from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import PlayerModel, PracticeRegisterModel, TournamentModel, TournamentMatrixModel
from collections import defaultdict
from flask import session

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/dashboard-minutes')
@login_required
def dashboard_minutes():

    season_id = session.get('season_id')
    players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id).order_by(PlayerModel.name).all()
    registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()

    # Step 1: Get the current user's tournament IDs
    user_tournament_ids = [t.id for t in TournamentModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()]

    # Step 2: Filter matrix entries to only those tournaments
    matrix_entries = TournamentMatrixModel.query.filter(
        TournamentMatrixModel.tournament_id.in_(user_tournament_ids),
        TournamentMatrixModel.played == True
    ).all()

    from collections import defaultdict
    dashboard_data = defaultdict(lambda: {"minutes_played": 0, "practice_minutes": 0})

    # Minutes played from Tournament Matrix
    for entry in matrix_entries:
        dashboard_data[entry.player_name]["minutes_played"] += 6  # 6 minutes per period

    # Practice minutes from Practice Register
    for reg in registers:
        duration = reg.duration_minutes or 0
        for p in reg.players_present.split(','):
            name = p.strip()
            if name:
                dashboard_data[name]["practice_minutes"] += duration

    # Prepare chart data
    labels = list(dashboard_data.keys())
    minutes_played = [dashboard_data[name]["minutes_played"] for name in labels]
    practice_minutes = [dashboard_data[name]["practice_minutes"] for name in labels]

    return render_template("dashboard_minutes.html",
                           players=players,
                           data=dashboard_data,
                           chart_labels=labels,
                           chart_played=minutes_played,
                           chart_practiced=practice_minutes)

@dashboard_bp.route('/dashboard-totals')
@login_required
def dashboard_totals():

    season_id = session.get('season_id')
    players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id).order_by(PlayerModel.name).all()
    totals_data = defaultdict(lambda: {"games_played": 0, "practices_attended": 0})

    # Initialize all players
    for player in players:
        totals_data[player.name]

    # Step 1: Get the current user's tournament IDs
    user_tournament_ids = [t.id for t in TournamentModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()]

    # Step 2: Filter matrix entries to only those tournaments
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
    
    # print(totals_data)
    
    return render_template('dashboard_totals.html',
                           players=players,
                           totals_data=totals_data)