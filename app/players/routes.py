from flask import Blueprint, render_template, request, redirect, session
from flask_login import login_required, current_user
from ..models import PlayerModel  
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