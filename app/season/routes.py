from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_required, current_user
from app.models import SeasonModel, PlayerModel
from app.extensions import db

season_bp = Blueprint('season', __name__, url_prefix='/season')

@season_bp.route('/manage', methods=['GET', 'POST'])
@login_required
def manage_seasons():
    if request.method == 'POST':
        name = request.form['name']
        year = request.form.get('year', '')

        new_season = SeasonModel(name=name, year=year, user_id=current_user.id)
        db.session.add(new_season)
        db.session.commit()

        # ✅ If user selected to copy players from the current season
        if request.form.get('copy_players') == 'on':
            current_season_id = session.get('season_id')
            if current_season_id:
                current_players = PlayerModel.query.filter_by(
                    user_id=current_user.id,
                    season_id=current_season_id
                ).all()

                for p in current_players:
                    copied = PlayerModel(
                        user_id=p.user_id,
                        season_id=new_season.id,
                        name=p.name,
                        dob=p.dob,
                        mobile_phone=p.mobile_phone,
                        email=p.email,
                        escalao=p.escalao,
                        n_carteira=p.n_carteira
                    )
                    db.session.add(copied)
                db.session.commit()

        # ✅ Auto-select the new season after creation
        session['season_id'] = new_season.id
        return redirect(url_for('season.manage_seasons'))

    seasons = SeasonModel.query.filter_by(user_id=current_user.id).order_by(SeasonModel.created_at.desc()).all()
    current_season_id = session.get('season_id')
    return render_template('manage_seasons.html', seasons=seasons, current_season_id=current_season_id)

@season_bp.route('/set-season', methods=['POST'])
@login_required
def set_season():
    selected = request.form.get('season_id')
    if selected:
        session['season_id'] = int(selected)
    return redirect(request.referrer or url_for('home.dashboard'))