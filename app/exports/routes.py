from flask import Blueprint, send_file, current_app
from flask_login import login_required, current_user
from io import BytesIO, StringIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from collections import defaultdict
import csv
from flask import make_response

from app.models import TournamentModel, TournamentMatrixModel, PlayerModel, PracticeRegisterModel

export_bp = Blueprint('export', __name__, url_prefix='/export')

@export_bp.route('/tournament/<int:tournament_id>/pdf')
@login_required
def generate_tournament_pdf(tournament_id):
    tournament = TournamentModel.query.get_or_404(tournament_id)

    if tournament.user_id != current_user.id:
        return "⛔ Unauthorized", 403

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
    tournament = TournamentModel.query.get_or_404(tournament_id)

    if tournament.user_id != current_user.id:
        return "⛔ Unauthorized", 403

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
    players = PlayerModel.query.filter_by(user_id=current_user.id).order_by(PlayerModel.name).all()
    registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id).all()

    user_tournament_ids = [t.id for t in TournamentModel.query.filter_by(user_id=current_user.id).all()]
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
    
    players = PlayerModel.query.filter_by(user_id=current_user.id).order_by(PlayerModel.name).all()
    totals_data = defaultdict(lambda: {"games_played": 0, "practices_attended": 0})

    user_tournament_ids = [t.id for t in TournamentModel.query.filter_by(user_id=current_user.id).all()]
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

    practice_registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id).all()
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