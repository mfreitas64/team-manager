from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_required, current_user
from app import db
from app.models import PlayerModel, PracticeExerciseModel, PracticeRegisterModel
from datetime import datetime, timedelta

practise_bp = Blueprint('practise', __name__, url_prefix='/practise')

@practise_bp.route('/practice-register', methods=['GET', 'POST'])
@login_required
def practice_register():
    
    season_id = session.get('season_id')

    if not season_id:
        return redirect(url_for('season.manage_seasons'))

    raw_players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()
    all_players = sorted(
    [{"name": p.name, "alias": p.alias or p.name} for p in raw_players],
    key=lambda x: x["alias"].lower())
    alias_lookup = {p["name"]: p["alias"] for p in all_players}

    all_exercises = PracticeExerciseModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()

    if request.method == 'POST':
        date_str = request.form['date']
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        notes = request.form.get('coach_notes', '')
        players_present = ','.join(request.form.getlist('players'))
        exercises_used = ','.join(request.form.getlist('exercises'))
        duration = request.form.get('duration_minutes', 0)

        register = PracticeRegisterModel(
            user_id=current_user.id,
            season_id=season_id,
            date=date_obj,
            players_present=players_present,
            exercises_used=exercises_used,
            coach_notes=notes,
            duration_minutes=duration
        )
        db.session.add(register)
        db.session.commit()
        return redirect(url_for('practise.practice_register'))

    # 📅 Filter by from_date or default to 2 weeks ago
    filter_date_str = request.args.get('from_date')
    if filter_date_str:
        try:
            from_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
        except ValueError:
            from_date = datetime.today().date() - timedelta(weeks=40)
    else:
        from_date = datetime.today().date() - timedelta(weeks=40)

    past_registers = PracticeRegisterModel.query.filter(
        PracticeRegisterModel.user_id == current_user.id,
        PracticeRegisterModel.season_id == season_id,
        PracticeRegisterModel.date >= from_date
    ).order_by(PracticeRegisterModel.date.desc()).all()

    # 🧠 Build exercise labels
    exercise_map = {str(e.id): f"{e.category} – {e.execution_description[:40]}..." for e in all_exercises}

    for r in past_registers:
        if r.exercises_used:
            r.exercise_labels = [exercise_map.get(eid.strip(), f"ID {eid.strip()}") for eid in r.exercises_used.split(',')]
        else:
            r.exercise_labels = []

    return render_template(
        'practice_register.html',
        players=all_players,
        exercises=all_exercises,
        registers=past_registers,
        from_date=filter_date_str,
        alias_lookup=alias_lookup  
    )

@practise_bp.route('/practice-register/<int:register_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_practice_register(register_id):

    season_id=session.get('season_id')

    if not season_id:
        return redirect(url_for('season.manage_seasons'))  # or return a default response
    
    register = PracticeRegisterModel.query.get_or_404(register_id)

    # 🔐 Prevent editing others' data
    if register.user_id != current_user.id or register.season_id != season_id:
        return "⛔️ Unauthorized", 403

    raw_players = PlayerModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()
    all_players = sorted(
    [{"name": p.name, "alias": p.alias or p.name} for p in raw_players],
    key=lambda x: x["alias"].lower())

    all_exercises = PracticeExerciseModel.query.filter_by(user_id=current_user.id, season_id=season_id).all()

    if request.method == 'POST':
        date_str = request.form['date']
        register.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        register.players_present = ','.join(request.form.getlist('players'))
        register.exercises_used = ','.join(request.form.getlist('exercises'))
        register.coach_notes = request.form.get('coach_notes', '')
        register.duration_minutes = int(request.form.get('duration_minutes', 0))
        db.session.commit()
        return redirect(url_for('practise.practice_register'))

    selected_players = register.players_present.split(',') if register.players_present else []
    selected_exercises = register.exercises_used.split(',') if register.exercises_used else []

    return render_template("edit_practice_register.html",
                           register=register,
                           players=all_players,
                           exercises=all_exercises,
                           selected_players=selected_players,
                           selected_exercises=selected_exercises)

@practise_bp.route('/practice-exercises', methods=['GET', 'POST'])
@login_required
def practice_exercises():

    season_id = session.get('season_id')

    if not season_id:
        return redirect(url_for('season.manage_seasons'))
    
    if request.method == 'POST':
        season_id = session.get('season_id')
        new_exercise = PracticeExerciseModel(
            user_id=current_user.id,  # 🔐 associate with current user
            season_id=season_id,
            category=request.form['category'],
            needed_material=request.form['needed_material'],
            execution_description=request.form['execution_description'],
            image1=request.form.get('image1'),
            image2=request.form.get('image2'),
            image3=request.form.get('image3'),
            image4=request.form.get('image4'),
            creation_date=datetime.now().strftime("%Y-%m-%d")  # optional: ensure it's set
        )
        db.session.add(new_exercise)
        db.session.commit()
        return redirect(url_for('practise.practice_exercises', open='form'))

    open_form = request.args.get('open') == 'form'
    
    # 🔐 Only show this user's exercises
    exercises = PracticeExerciseModel.query.filter_by(user_id=current_user.id, season_id=season_id).order_by(PracticeExerciseModel.creation_date.desc()).all()

    return render_template("practice_exercises.html", exercises=exercises, open_form=open_form)

@practise_bp.route('/practice-exercise/<int:exercise_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_practice_exercise(exercise_id):

    season_id = session.get('season_id')

    if not season_id:
        return redirect(url_for('season.manage_seasons'))

    exercise = PracticeExerciseModel.query.get_or_404(exercise_id)

    # 🔐 Prevent editing another user's exercise
    if exercise.user_id != current_user.id or exercise.season_id != season_id:
        return "⛔️ Unauthorized access", 403
    
    if request.method == 'POST':
        exercise.category = request.form['category']
        exercise.needed_material = request.form['needed_material']
        exercise.execution_description = request.form['execution_description']
        exercise.image1 = request.form.get('image1')
        exercise.image2 = request.form.get('image2')
        exercise.image3 = request.form.get('image3')
        exercise.image4 = request.form.get('image4')
        db.session.commit()
        return redirect(url_for('practise.practice_exercises'))

    return render_template("edit_practice_exercise.html", exercise=exercise)

@practise_bp.route('/practice-exercise/<int:exercise_id>/delete', methods=['POST'])
@login_required
def delete_practice_exercise(exercise_id):

    season_id = session.get('season_id')
    
    if not season_id:
        return redirect(url_for('season.manage_seasons'))  # or return a default response
    
    exercise = PracticeExerciseModel.query.get_or_404(exercise_id)

    # 🔐 Ensure user owns it
    if exercise.user_id != current_user.id or exercise.season_id != season_id:
        return "⛔ Unauthorized", 403
    
    db.session.delete(exercise)
    db.session.commit()
    return redirect(url_for('practise.practice_exercises'))

@practise_bp.route('/practice-register/<int:register_id>/delete', methods=['POST'])
@login_required
def delete_practice_register(register_id):

    season_id = session.get('season_id')
    
    if not season_id:
        return redirect(url_for('season.manage_seasons'))
        
    register = PracticeRegisterModel.query.get_or_404(register_id)

    if register.user_id != current_user.id or register.season_id != season_id:
        return "⛔ Unauthorized", 403
    
    db.session.delete(register)
    db.session.commit()
    return redirect(url_for('practise.practice_register'))
