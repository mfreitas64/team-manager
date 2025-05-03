from flask import Blueprint, render_template, request, redirect
from flask_login import login_required, current_user
from ..models import PlayerModel  
from .. import db 
from flask import url_for                

players_bp = Blueprint('players', __name__, url_prefix='/players')

@players_bp.route('/', methods=['GET', 'POST'])
@login_required
def manage_players():
    if request.method == 'POST':
        new_player = PlayerModel(
            user_id=current_user.id,
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

    all_players = PlayerModel.query.filter_by(user_id=current_user.id).all()
    return render_template('players.html', players=all_players)

@players_bp.route('/player/<int:player_id>/delete', methods=['POST'])
@login_required
def delete_player(player_id):
    player = PlayerModel.query.get_or_404(player_id)

    # 🔐 Make sure the player belongs to the logged-in user
    if player.user_id != current_user.id:
        return "⛔ Unauthorized", 403

    db.session.delete(player)
    db.session.commit()
    return redirect(url_for('players.manage_players'))