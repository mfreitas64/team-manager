from flask import Blueprint, render_template, request, redirect, session
from flask_login import login_required, current_user
from ..models import PlayerModel, PlayerSeasonStatsModel, PracticeRegisterModel, TournamentMatrixModel  
from .. import db 
from flask import url_for                

players_bp = Blueprint('players', __name__, url_prefix='/players')

@players_bp.route('/', methods=['GET', 'POST'])
@login_required
def manage_players():

    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))
    
    if request.method == 'POST':
        new_player = PlayerModel(
            user_id=current_user.id,
            season_id=season_id,
            season_year=request.form['season_year'],
            name=request.form['name'],
            escalao=request.form['escalao'],
            n_carteira=request.form['n_carteira'],
            dob=request.form['dob'],
            mobile_phone=request.form['mobile_phone'],
            email=request.form['email']
        )
        db.session.add(new_player)
        db.session.commit()
        return redirect('/players')

    all_players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()
    return render_template('players.html', players=all_players)

@players_bp.route('/player/<int:player_id>/delete', methods=['POST'])
@login_required
def delete_player(player_id):

    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))

    player = PlayerModel.query.get_or_404(player_id)

    # 🔐 Make sure the player belongs to the logged-in user
    if player.user_id != current_user.id or player.season_id != season_id:
        return "⛔ Unauthorized", 403

    db.session.delete(player)
    db.session.commit()
    return redirect(url_for('players.manage_players'))

@players_bp.route('/player/<int:player_id>/season-stats', methods=['GET', 'POST'])
@login_required
def player_season_stats(player_id):
    season_id = session.get('season_id')
    if not season_id:
        return redirect(url_for('season.manage_seasons'))

    player = PlayerModel.query.get_or_404(player_id)

    # 🔐 Verify ownership and season
    if player.user_id != current_user.id or player.season_id != season_id:
        return "⛔ Unauthorized", 403

    # Try to find existing stats or create new
    stats = PlayerSeasonStatsModel.query.filter_by(player_id=player.id, season_id=season_id).first()
    if not stats:
        stats = PlayerSeasonStatsModel(player_id=player.id, season_id=season_id)
        db.session.add(stats)
        db.session.commit()

    if request.method == 'POST':
        stats.behavior = request.form.get('behavior')
        stats.technical_skills = request.form.get('technical_skills')
        stats.team_relation = request.form.get('team_relation')
        stats.improvement_areas = request.form.get('improvement_areas')
        stats.height_cm = request.form.get('height_cm') or None
        stats.weight_kg = request.form.get('weight_kg') or None
        db.session.commit()
        return redirect(url_for('players.manage_players'))

    return render_template('player_season_stats.html', player=player, stats=stats)

@players_bp.route('/player/<int:player_id>/history')
@login_required
def player_history(player_id):
    player = PlayerModel.query.get_or_404(player_id)

    # 🔐 Make sure player belongs to the user
    if player.user_id != current_user.id:
        return "⛔ Unauthorized", 403

    # ✅ Fetch all seasons for this user/player
    all_stats = PlayerSeasonStatsModel.query.filter_by(player_id=player_id).all()
    all_registers = PracticeRegisterModel.query.filter_by(user_id=current_user.id).all()
    all_matrix_entries = TournamentMatrixModel.query.filter_by(user_id=current_user.id).filter_by(played=True).all()

    # 🔢 Aggregate stats
    total_practices = 0
    for r in all_registers:
        if r.players_present and player.name in r.players_present:
            total_practices += 1

    total_games = sum(1 for entry in all_matrix_entries if entry.player_name == player.name)

    # 🧠 Latest stats entry (optional)
    latest_stats = all_stats[-1] if all_stats else None

    return render_template('player_history.html',
                           player=player,
                           stats_entries=all_stats,
                           total_practices=total_practices,
                           total_games=total_games,
                           latest_stats=latest_stats)