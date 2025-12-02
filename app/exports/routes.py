from flask import Blueprint, send_file, current_app, make_response, session, url_for, redirect, request, render_template, send_file
from flask_login import login_required, current_user
from io import BytesIO, StringIO
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from collections import defaultdict
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False
    print("⚠️ WeasyPrint not available - some PDF exports will be disabled")
from datetime import datetime
import csv
import os
import base64
from reportlab.platypus import Image as PlatypusImage

from app.models import TournamentModel, TournamentMatrixModel, PlayerModel, PracticeRegisterModel, PlayerSeasonStatsModel, SeasonModel, PracticeExerciseModel

export_bp = Blueprint('export', __name__, url_prefix='/export')
    
def encode_image_base64(path):
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"

@export_bp.route('/tournament/<int:tournament_id>/pdf')
@login_required
def generate_tournament_pdf(tournament_id):

    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))  # or return a default response

    tournament = TournamentModel.query.get_or_404(tournament_id)

    if tournament.user_id != current_user.id:
        return "⛔ Unauthorized", 403
    
    season_id = session.get('season_id')
    if tournament.season_id != season_id:
        return "⛔ Tournament is not in current season", 403

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    margin = 40
    y_start = height - margin
    x_start = margin

    players = [p.strip() for p in tournament.players.split(',') if p.strip()]
    opponents = [op.strip() for op in tournament.opponents.split(',') if op.strip()]
    periods_per_opponent = 4
    player_col_width = 100
    period_col_width = 25
    cell_height = 15
    table_top_y = y_start - 60

    matrix_entries = TournamentMatrixModel.query.filter_by(tournament_id=tournament_id).all()
    matrix_lookup = {
        (entry.player_name.strip(), entry.opponent_name.strip(), entry.period): entry.played
        for entry in matrix_entries
    }

    minutes_played = defaultdict(int)
    for entry in matrix_entries:
        if entry.played:
            minutes_played[entry.player_name.strip()] += 6

    if tournament.coach_notes:
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(x_start, y_start - 40, f"Coach Notes: {tournament.coach_notes[:120]}")

    c.setFont("Helvetica-Bold", 13)
    c.drawString(x_start, y_start, f"{tournament.team_name} - Tournament Sheet")
    c.setFont("Helvetica", 10)
    c.drawString(x_start, y_start - 20, f"Date: {tournament.date}     Place: {tournament.place}")

    c.setFont("Helvetica-Bold", 8)
    for i, opponent in enumerate(opponents):
        base_x = x_start + player_col_width + (i * periods_per_opponent * period_col_width)
        block_width = periods_per_opponent * period_col_width
        c.drawCentredString(base_x + block_width / 2, table_top_y, opponent)
        for p in range(periods_per_opponent):
            px = base_x + (p * period_col_width)
            c.drawCentredString(px + period_col_width / 2, table_top_y - 10, f"P{p + 1}")

    y = table_top_y - 35
    c.setFont("Helvetica", 7)
    for player in players:
        label = f"{player} ({minutes_played.get(player, 0)} min)"
        c.drawRightString(x_start + player_col_width - 5, y + 4, label)
        x = x_start + player_col_width
        for opponent in opponents:
            for period in range(1, 5):
                cell_played = matrix_lookup.get((player, opponent, period), False)
                c.rect(x, y, period_col_width, cell_height, stroke=1, fill=0)
                if cell_played:
                    c.drawCentredString(x + period_col_width / 2, y + 3, "X")
                x += period_col_width
        y -= cell_height
        if y < 40:
            c.showPage()
            y = height - margin - 60

    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name=f"tournament_{tournament.id}_sheet.pdf",
                     mimetype='application/pdf')

@export_bp.route('/tournament/<int:tournament_id>/export/csv')
@login_required
def export_tournament_csv(tournament_id):

    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))  # or return a default response

    tournament = TournamentModel.query.get_or_404(tournament_id)

    if tournament.user_id != current_user.id:
        return "⛔ Unauthorized", 403
    
    season_id = session.get('season_id')
    if tournament.season_id != season_id:
        return "⛔ Tournament is not in current season", 403

    matrix_entries = TournamentMatrixModel.query.filter_by(tournament_id=tournament_id).all()

    # Write to a text buffer
    text_buffer = StringIO()
    writer = csv.writer(text_buffer)
    writer.writerow(["Player", "Opponent", "Period", "Played"])

    for entry in matrix_entries:
        writer.writerow([
            entry.player_name,
            entry.opponent_name,
            f"P{entry.period}",
            "Yes" if entry.played else "No"
        ])

    # Convert to bytes
    bytes_buffer = BytesIO()
    bytes_buffer.write(text_buffer.getvalue().encode('utf-8'))
    bytes_buffer.seek(0)

    return send_file(
        bytes_buffer,
        as_attachment=True,
        download_name=f"tournament_{tournament.id}_matrix.csv",
        mimetype='text/csv'
    )

@export_bp.route('/minutes/csv')
@login_required
def export_minutes_csv():

    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))  # or return a default response

    players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id).order_by(PlayerModel.name).all()
    registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()

    user_tournament_ids = [t.id for t in TournamentModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()]
    matrix_entries = TournamentMatrixModel.query.filter(
        TournamentMatrixModel.tournament_id.in_(user_tournament_ids),
        TournamentMatrixModel.played == True
    ).all()

    dashboard_data = defaultdict(lambda: {"minutes_played": 0, "practice_minutes": 0})

    for entry in matrix_entries:
        dashboard_data[entry.player_name]["minutes_played"] += 6

    for reg in registers:
        duration = reg.duration_minutes or 0
        for p in reg.players_present.split(','):
            name = p.strip()
            if name:
                dashboard_data[name]["practice_minutes"] += duration

    # Prepare CSV
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Player", "Minutes Played", "Practice Minutes", "Total Minutes"])

    for player in players:
        stats = dashboard_data.get(player.name, {'minutes_played': 0, 'practice_minutes': 0})
        writer.writerow([
            player.name,
            stats["minutes_played"],
            stats["practice_minutes"],
            stats["minutes_played"] + stats["practice_minutes"]
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=dashboard_minutes.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@export_bp.route('/totals/csv')
@login_required
def export_totals_csv():

    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))  # or return a default response
    
    players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id).order_by(PlayerModel.name).all()
    totals_data = defaultdict(lambda: {"games_played": 0, "practices_attended": 0})

    user_tournament_ids = [t.id for t in TournamentModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()]
    matrix_entries = TournamentMatrixModel.query.filter(
        TournamentMatrixModel.tournament_id.in_(user_tournament_ids),
        TournamentMatrixModel.played == True
    ).all()

    seen_games = set()
    for entry in matrix_entries:
        key = (entry.player_name.strip(), entry.tournament_id, entry.opponent_name.strip())
        if key not in seen_games:
            totals_data[entry.player_name.strip()]["games_played"] += 1
            seen_games.add(key)

    practice_registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()
    for reg in practice_registers:
        players_present = [p.strip() for p in reg.players_present.split(',') if p.strip()]
        for p in players_present:
            totals_data[p]["practices_attended"] += 1

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Player", "Games Played", "Practices Attended", "Total Activities"])

    for player in players:
        totals = totals_data.get(player.name, {'games_played': 0, 'practices_attended': 0})
        writer.writerow([
            player.name,
            totals["games_played"],
            totals["practices_attended"],
            totals["games_played"] + totals["practices_attended"]
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=dashboard_totals.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@export_bp.route('/export/players/csv')
@login_required
def export_players_csv():
    player_id = request.args.get('player_id')
    season_id = session.get('season_id')

    query = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id)
    if player_id:
        query = query.filter_by(id=player_id)

    players = query.all()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Alias', 'Name', 'Escalão', 'Carteira', 'DOB', 'Phone', 'Email'])

    for p in players:
        writer.writerow([p.alias or '', p.name, p.escalao, p.n_carteira, p.dob, p.mobile_phone, p.email])

    response = make_response(si.getvalue())
    filename = f"{'player' if player_id else 'all_players'}_export.csv"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Type'] = 'text/csv'
    return response

@export_bp.route('/export/players/pdf-html')
@login_required
def export_players_pdf_html():
    if not WEASYPRINT_AVAILABLE:
        return "WeasyPrint not available on this system. Please use CSV export or install GTK libraries.", 503
    
    player_id = request.args.get('player_id')
    season_id = session.get('season_id')
    season = SeasonModel.query.get(season_id)
    season_name = season.name if season else "Current Season"

    players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id)
    if player_id:
        players = players.filter_by(id=player_id)

    players = players.all()

    # Calculate stats dynamically per player
    registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()
    matrix_entries = TournamentMatrixModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()

    enriched = []
    for p in players:
        # Practice stats
        practice_minutes = 0
        total_practices = 0
        for r in registers:
            if p.name in (r.players_present or ""):
                practice_minutes += r.duration_minutes or 0
                total_practices += 1

        # Game stats
        game_minutes = 0
        games_seen = set()
        for entry in matrix_entries:
            if entry.player_name == p.name and entry.played:
                game_minutes += 6
                games_seen.add((entry.tournament_id, entry.opponent_name))

        total_games = len(games_seen)

        # Season evaluation fields
        stats = PlayerSeasonStatsModel.query.filter_by(player_id=p.id, season_id=season_id).first()

        enriched.append({
            "name": p.name,
            "alias": p.alias,
            "escalao": p.escalao,
            "n_carteira": p.n_carteira,
            "dob": p.dob,
            "mobile_phone": p.mobile_phone,
            "email": p.email,
            "practice_minutes": practice_minutes,
            "game_minutes": game_minutes,
            "total_practices": total_practices,
            "total_games": total_games,
            "behavior": getattr(stats, "behavior", "—"),
            "technical_skills": getattr(stats, "technical_skills", "—"),
            "team_relation": getattr(stats, "team_relation", "—"),
            "improvement_areas": getattr(stats, "improvement_areas", "—")
        })

    # Inline logo
    logo_path = os.path.join(current_app.root_path, "static", "logo_illiabum.jpg")
    logo_data = encode_image_base64(logo_path) if os.path.exists(logo_path) else None

    html = render_template(
        "player_pdf.html",
        players=enriched,
        logo_data=logo_data,
        season_name=season_name
    )

    pdf = BytesIO()
    HTML(string=html).write_pdf(pdf)
    pdf.seek(0)

    return send_file(
        pdf,
        mimetype="application/pdf",
        download_name="player_export.pdf",
        as_attachment=True
    )

@export_bp.route('/export/players/pdf-summary')
@login_required
def export_players_summary_pdf_html():
    if not WEASYPRINT_AVAILABLE:
        return "WeasyPrint not available on this system. Please use CSV export or install GTK libraries.", 503
    
    season_id = session.get('season_id')

    players = PlayerModel.query.filter_by(
        user_id=current_user.id,
        season_id=season_id
    ).order_by(
        PlayerModel.escalao,
        PlayerModel.n_carteira,
        PlayerModel.dob
    ).all()

    logo_path = os.path.join(current_app.root_path, "static", "logo_illiabum.jpg")
    logo_data = encode_image_base64(logo_path) if os.path.exists(logo_path) else None

    html = render_template(
        "players_summary.html",
        players=players,
        logo_data=logo_data,
        now=datetime.now()
    )

    pdf = BytesIO()
    HTML(string=html).write_pdf(pdf)
    pdf.seek(0)

    return send_file(
        pdf,
        mimetype="application/pdf",
        download_name="players_summary.pdf",
        as_attachment=True
    )

@export_bp.route('/practice-register/pdf')
@login_required
def export_practice_register_pdf():
    """Export practice register to PDF for a selected month in tabular format"""
    
    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))

    # Get month/year from query params (default to current month)
    year = request.args.get('year', type=int) or datetime.now().year
    month = request.args.get('month', type=int) or datetime.now().month

    # Calculate date range for the month
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start_date = datetime(year, month, 1).date()
    end_date = datetime(year, month, last_day).date()

    # Get practice registers for the month
    registers = PracticeRegisterModel.query.filter(
        PracticeRegisterModel.user_id == current_user.id,
        PracticeRegisterModel.season_id == season_id,
        PracticeRegisterModel.date >= start_date,
        PracticeRegisterModel.date <= end_date
    ).order_by(PracticeRegisterModel.date.asc()).all()

    # Get all players sorted by name
    raw_players = PlayerModel.query.filter_by(
        user_id=current_user.id, 
        season_id=season_id
    ).order_by(PlayerModel.name).all()
    
    # Get season name
    season = SeasonModel.query.get(season_id)
    season_name = season.name if season else f"Season {season_id}"

    # Build attendance matrix: player_name -> {date -> present}
    attendance = {}
    practice_dates = []
    
    for reg in registers:
        practice_dates.append(reg.date)
        players_present = [p.strip() for p in reg.players_present.split(',') if p.strip()]
        
        for player in raw_players:
            if player.name not in attendance:
                attendance[player.name] = {}
            attendance[player.name][reg.date] = player.name in players_present

    # Generate PDF using ReportLab (Landscape for better width)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    margin = 30
    y = height - margin
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    title = f"{month_names[month]} {year} - Practice Attendance"
    c.drawCentredString(width / 2, y, title)
    y -= 20
    
    # Season info
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, f"Season: {season_name}")
    y -= 25

    if not practice_dates:
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(margin, y, "No practice sessions recorded for this month.")
        c.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True,
                        download_name=f"practice_register_{year}_{month:02d}.pdf",
                        mimetype='application/pdf')

    # Calculate table dimensions
    player_col_width = 180  # Increased width for full names
    num_practices = len(practice_dates)
    date_col_width = max(35, min(50, (width - margin * 2 - player_col_width) / num_practices))
    cell_height = 18
    
    table_y = y
    x_start = margin
    
    # Draw header row - Practice dates
    c.setFont("Helvetica-Bold", 7)
    
    # Player name column header
    c.setFillColor(colors.HexColor('#eb6636'))  # Coral theme
    c.rect(x_start, table_y - cell_height, player_col_width, cell_height, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.drawString(x_start + 5, table_y - cell_height + 6, "Player Name")
    
    # Date column headers
    for idx, practice_date in enumerate(practice_dates):
        x = x_start + player_col_width + (idx * date_col_width)
        c.setFillColor(colors.HexColor('#eb6636'))
        c.rect(x, table_y - cell_height, date_col_width, cell_height, fill=1, stroke=1)
        c.setFillColor(colors.white)
        date_str = practice_date.strftime('%d/%m')
        c.drawCentredString(x + date_col_width / 2, table_y - cell_height + 6, date_str)
    
    table_y -= cell_height
    
    # Draw player rows
    c.setFillColor(colors.black)
    for player in raw_players:
        # Check if we need a new page
        if table_y < 60:
            c.showPage()
            table_y = height - margin
            
            # Redraw headers on new page
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(colors.HexColor('#eb6636'))
            c.rect(x_start, table_y - cell_height, player_col_width, cell_height, fill=1, stroke=1)
            c.setFillColor(colors.white)
            c.drawString(x_start + 5, table_y - cell_height + 6, "Player Name")
            
            for idx, practice_date in enumerate(practice_dates):
                x = x_start + player_col_width + (idx * date_col_width)
                c.setFillColor(colors.HexColor('#eb6636'))
                c.rect(x, table_y - cell_height, date_col_width, cell_height, fill=1, stroke=1)
                c.setFillColor(colors.white)
                date_str = practice_date.strftime('%d/%m')
                c.drawCentredString(x + date_col_width / 2, table_y - cell_height + 6, date_str)
            
            table_y -= cell_height
            c.setFillColor(colors.black)
        
        # Player name cell
        c.setFont("Helvetica", 7)
        c.rect(x_start, table_y - cell_height, player_col_width, cell_height, stroke=1, fill=0)
        player_name = player.name
        # Truncate if too long
        if len(player_name) > 32:
            player_name = player_name[:29] + "..."
        c.drawString(x_start + 5, table_y - cell_height + 6, player_name)
        
        # Attendance cells
        c.setFont("Helvetica-Bold", 10)
        for idx, practice_date in enumerate(practice_dates):
            x = x_start + player_col_width + (idx * date_col_width)
            c.rect(x, table_y - cell_height, date_col_width, cell_height, stroke=1, fill=0)
            
            # Mark P for present, F for absent
            if player.name in attendance and practice_date in attendance[player.name]:
                if attendance[player.name][practice_date]:
                    c.setFillColor(colors.green)
                    c.drawCentredString(x + date_col_width / 2, table_y - cell_height + 5, "P")
                else:
                    c.setFillColor(colors.red)
                    c.drawCentredString(x + date_col_width / 2, table_y - cell_height + 5, "F")
                c.setFillColor(colors.black)
        
        table_y -= cell_height
    
    # Summary statistics at bottom - NEW PAGE for all players
    c.showPage()
    y_summary = height - margin
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y_summary, "Attendance Summary")
    y_summary -= 25
    
    c.setFont("Helvetica-Bold", 10)
    total_practices = len(practice_dates)
    c.drawString(margin, y_summary, f"📊 Total Practices: {total_practices}")
    y_summary -= 20
    
    # Calculate attendance percentages for ALL players and sort by percentage
    player_stats = []
    for player in raw_players:
        if player.name in attendance:
            present_count = sum(1 for attended in attendance[player.name].values() if attended)
            percentage = (present_count / total_practices * 100) if total_practices > 0 else 0
            player_stats.append({
                'name': player.name,
                'present_count': present_count,
                'percentage': percentage
            })
    
    # Sort by percentage descending
    player_stats.sort(key=lambda x: x['percentage'], reverse=True)
    
    c.setFont("Helvetica", 8)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, y_summary, "Player")
    c.drawString(margin + 200, y_summary, "Attended")
    c.drawString(margin + 280, y_summary, "Percentage")
    y_summary -= 15
    
    c.setFont("Helvetica", 8)
    for stat in player_stats:
        if y_summary < 60:
            c.showPage()
            y_summary = height - margin
            c.setFont("Helvetica-Bold", 8)
            c.drawString(margin, y_summary, "Player")
            c.drawString(margin + 200, y_summary, "Attended")
            c.drawString(margin + 280, y_summary, "Percentage")
            y_summary -= 15
            c.setFont("Helvetica", 8)
        
        player_display = stat['name'] if len(stat['name']) <= 35 else stat['name'][:32] + "..."
        c.drawString(margin, y_summary, player_display)
        c.drawString(margin + 200, y_summary, f"{stat['present_count']}/{total_practices}")
        c.drawString(margin + 280, y_summary, f"{stat['percentage']:.0f}%")
        y_summary -= 12

    c.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True,
                    download_name=f"practice_register_{year}_{month:02d}.pdf",
                    mimetype='application/pdf')

    c.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True,
                    download_name=f"practice_register_{year}_{month:02d}.pdf",
                    mimetype='application/pdf')