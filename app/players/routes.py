from flask import Blueprint, render_template, request, redirect
from flask_login import login_required, current_user
from ..models import PlayerModel  
from .. import db                 

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