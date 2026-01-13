from flask import Blueprint, render_template, request, redirect, flash, url_for, session
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import UserModel, SeasonModel
from app.extensions import db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = UserModel.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)

            # ✅ Restore last selected season (or fall back to newest season)
            season_id = None
            if user.last_season_id:
                season = SeasonModel.query.filter_by(id=user.last_season_id, user_id=user.id).first()
                if season:
                    season_id = season.id

            if season_id is None:
                newest = SeasonModel.query.filter_by(user_id=user.id).order_by(SeasonModel.created_at.desc()).first()
                if newest:
                    season_id = newest.id
                    user.last_season_id = newest.id
                    db.session.commit()

            if season_id is not None:
                session['season_id'] = season_id

            return redirect('/')
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('season_id', None)
    return redirect('/auth/login')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        hashed_pw = generate_password_hash(password)
        new_user = UserModel(username=username, email=email, password_hash=hashed_pw)

        db.session.add(new_user)
        db.session.commit()

        return redirect('/auth/login')
    return render_template('signup.html')