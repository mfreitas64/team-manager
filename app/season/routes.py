from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_required, current_user
from app.models import SeasonModel
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
        session['season_id'] = new_season.id  # Auto-select after creation
        return redirect(url_for('season.manage_seasons'))

    seasons = SeasonModel.query.filter_by(user_id=current_user.id).order_by(SeasonModel.created_at.desc()).all()
    return render_template('manage_seasons.html', seasons=seasons)

@season_bp.route('/set-season', methods=['POST'])
@login_required
def set_season():
    selected = request.form.get('season_id')
    if selected:
        session['season_id'] = int(selected)
    return redirect(request.referrer or url_for('home.dashboard'))