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