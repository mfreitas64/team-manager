from flask import Blueprint, send_file, current_app, make_response, session, url_for, redirect, request, render_template, send_file
from flask_login import login_required, current_user
from io import BytesIO, StringIO
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from collections import defaultdict
from weasyprint import HTML
from datetime import datetime
import csv
import os
import base64
from reportlab.platypus import Image as PlatypusImage

from app.models import TournamentModel, TournamentMatrixModel, PlayerModel, PracticeRegisterModel, PlayerSeasonStatsModel, SeasonModel

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

@export_bp.route('/export/players/pdf')
@login_required
def export_players_pdf():
    player_id = request.args.get('player_id')
    season_id = session.get('season_id')

    if not season_id:
        return redirect(url_for('season.manage_seasons'))

    season = SeasonModel.query.get(season_id)
    season_title = season.name if season else "Current Season"

    query = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id)
    if player_id:
        query = query.filter_by(id=player_id)

    players = query.all()

    registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()
    tournament_ids = [t.id for t in TournamentModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()]
    matrix_entries = TournamentMatrixModel.query.filter(
        TournamentMatrixModel.tournament_id.in_(tournament_ids)
    ).all()

    stats_lookup = defaultdict(lambda: {"practice_minutes": 0, "total_practices": 0, "game_minutes": 0, "total_games": 0})
    seen_games = set()

    for reg in registers:
        if reg.players_present:
            for name in reg.players_present.split(','):
                name = name.strip()
                stats_lookup[name]["practice_minutes"] += reg.duration_minutes or 0
                stats_lookup[name]["total_practices"] += 1

    for entry in matrix_entries:
        if entry.played:
            stats_lookup[entry.player_name.strip()]["game_minutes"] += 6
            key = (entry.player_name.strip(), entry.tournament_id, entry.opponent_name.strip())
            if key not in seen_games:
                stats_lookup[entry.player_name.strip()]["total_games"] += 1
                seen_games.add(key)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    logo_path = os.path.join(current_app.root_path, 'static', 'logo_illiabum.jpg')

    for player in players:
        stats = stats_lookup[player.name]
        season_stats = PlayerSeasonStatsModel.query.filter_by(player_id=player.id, season_id=season_id).first()

        # Logo
        if os.path.exists(logo_path):
            try:
                img = PlatypusImage(logo_path, width=2.5*cm, height=2.5*cm)
                img.drawOn(pdf, 2*cm, height - 3*cm)
            except Exception as e:
                print("Logo draw error:", e)

        # Header
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(6*cm, height - 2.5*cm, player.name)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(6*cm, height - 3.2*cm, season_title)

        y = height - 4.5*cm
        section_x = 1.9 * cm
        section_width = 17 * cm

        def section_header(title):
            nonlocal y
            y -= 0.5*cm
            pdf.setFillColor(colors.HexColor("#003366"))  # blue header
            pdf.rect(section_x, y - 0.2*cm, section_width, 0.9*cm, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 13)
            pdf.drawString(section_x + 0.5*cm, y, title)
            y -= 1.1*cm
            pdf.setFillColor(colors.black)

        def draw_section_box(y_start, y_end):
            box_height = y_start - y_end + 0.5*cm
            pdf.setStrokeColor(colors.black)
            pdf.setLineWidth(0.5)
            pdf.rect(section_x, y_end - 0.2*cm, section_width, box_height, stroke=1, fill=0)

        def line(label, value):
            nonlocal y
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(section_x + 0.5*cm, y, f"{label}:")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(section_x + 4.5*cm, y, str(value) if value else "—")
            y -= 0.6*cm

        def multiline(label, text, width):
            nonlocal y
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(section_x + 0.5*cm, y, f"{label}:")
            y -= 0.5*cm
            pdf.setFont("Helvetica", 10)

            text = text or "—"
            lines = []
            line_text = ""
            for word in text.split():
                if pdf.stringWidth(line_text + " " + word) > width:
                    lines.append(line_text)
                    line_text = word
                else:
                    line_text = f"{line_text} {word}".strip()
            lines.append(line_text)

            for l in lines:
                pdf.drawString(section_x + 1*cm, y, l)
                y -= 0.5*cm

            y -= 0.4*cm  # extra gap between fields

        # 🔲 Personal Info
        y_start = y + 1.6*cm
        section_header("Personal Info")
        line("Alias", player.alias or "—")
        line("Escalão", player.escalao)
        line("Carteira Nº", player.n_carteira)
        line("Date of Birth", player.dob)
        line("Phone", player.mobile_phone)
        line("Email", player.email)
        draw_section_box(y_start, y)

        # 🔲 Season Stats
        y_start = y + 1.6*cm
        section_header("Season Stats")
        line("Minutes Practiced", stats["practice_minutes"])
        line("Minutes Played", stats["game_minutes"])
        line("Total Practices", stats["total_practices"])
        line("Total Games", stats["total_games"])
        draw_section_box(y_start, y)

        # 🔲 Coach Evaluation
        y_start = y + 1.6*cm
        section_header("Coach Evaluation")
        multiline("Behavior", getattr(season_stats, "behavior", "—"), width=15*cm)
        multiline("Technical Skills", getattr(season_stats, "technical_skills", "—"), width=15*cm)
        multiline("Team Relation", getattr(season_stats, "team_relation", "—"), width=15*cm)
        multiline("Improvement Areas", getattr(season_stats, "improvement_areas", "—"), width=15*cm)
        draw_section_box(y_start, y)

        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    filename = f"{'player' if player_id else 'all_players'}_export.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@export_bp.route('/players/pdf/summary')
@login_required
def export_players_summary_pdf():
    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))

    players = PlayerModel.query.filter_by(
        user_id=current_user.id,
        season_id=season_id
    ).order_by(PlayerModel.escalao, PlayerModel.n_carteira).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2 * cm, height - 2 * cm, "Team Roster – Summary Report")

    pdf.setFont("Helvetica-Bold", 10)
    headers = ["Nº Carteira", "Alias", "Name", "Escalão", "DOB", "Phone", "Email"]
    x_positions = [2*cm, 4.5*cm, 7.5*cm, 11*cm, 14*cm, 17*cm, 20*cm]

    y = height - 3*cm
    for i, header in enumerate(headers):
        pdf.drawString(x_positions[i], y, header)

    pdf.setFont("Helvetica", 9)
    y -= 0.7 * cm

    for player in players:
        row = [
            player.n_carteira,
            player.alias or "",
            player.name,
            player.escalao,
            str(player.dob),
            player.mobile_phone or "",
            player.email or ""
        ]
        for i, cell in enumerate(row):
            pdf.drawString(x_positions[i], y, str(cell))
        y -= 0.6 * cm
        if y < 2*cm:
            pdf.showPage()
            y = height - 2.5 * cm

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="players_summary.pdf", mimetype='application/pdf')

@export_bp.route('/export/players/pdf-html')
@login_required
def export_players_pdf_html():
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