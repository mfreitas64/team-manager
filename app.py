from flask import Flask, render_template, request, redirect, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from player import Player
from datetime import datetime, timezone
from io import BytesIO, StringIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
import csv
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)

# SQLite DB config
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database model
class PlayerModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_year = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    escalao = db.Column(db.String(50), nullable=False)
    n_carteira = db.Column(db.String(50), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    mobile_phone = db.Column(db.String(20))
    email = db.Column(db.String(100))

class PracticeExerciseModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    needed_material = db.Column(db.String(200))
    execution_description = db.Column(db.Text)
    image1 = db.Column(db.String(255))
    image2 = db.Column(db.String(255))
    image3 = db.Column(db.String(255))
    image4 = db.Column(db.String(255))
    creation_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class TournamentModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    place = db.Column(db.String(100), nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    opponents = db.Column(db.Text)  # comma-separated opponent names
    players = db.Column(db.Text)    # comma-separated player names
    coach_notes = db.Column(db.Text)  # Add this line

class TournamentMatrixModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament_model.id'), nullable=False)
    player_name = db.Column(db.String(100), nullable=False)
    opponent_name = db.Column(db.String(100), nullable=False)
    period = db.Column(db.Integer, nullable=False)  # 1 to 4
    played = db.Column(db.Boolean, default=False)

class PracticeRegisterModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    players_present = db.Column(db.Text)  # comma-separated player names
    exercises_used = db.Column(db.Text)   # comma-separated exercise IDs
    coach_notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)

# Initialize DB
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    player_count = PlayerModel.query.count()
    tournament_count = TournamentModel.query.count()
    practice_log_count = PracticeRegisterModel.query.count()

    return render_template('index.html',
                           player_count=player_count,
                           tournament_count=tournament_count,
                           practice_log_count=practice_log_count)

@app.route('/players', methods=['GET', 'POST'])
def manage_players():
    if request.method == 'POST':
        new_player = PlayerModel(
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
        return redirect('/players?open=form')  # 🔁 redirect with a flag

    open_form = request.args.get('open') == 'form'  # 👈 read the flag
    all_players = PlayerModel.query.all()
    return render_template('players.html', players=all_players, open_form=open_form)

@app.route('/practice-exercises', methods=['GET', 'POST'])
def practice_exercises():
    if request.method == 'POST':
        new_exercise = PracticeExerciseModel(
            category=request.form['category'],
            needed_material=request.form['needed_material'],
            execution_description=request.form['execution_description'],
            image1=request.form.get('image1'),
            image2=request.form.get('image2'),
            image3=request.form.get('image3'),
            image4=request.form.get('image4')
        )
        db.session.add(new_exercise)
        db.session.commit()
        return redirect('/practice-exercises?open=form')  # keeps form open after submit

    open_form = request.args.get('open') == 'form'
    exercises = PracticeExerciseModel.query.order_by(PracticeExerciseModel.creation_date.desc()).all()
    return render_template('practice_exercises.html', exercises=exercises, open_form=open_form)

@app.route('/tournaments', methods=['GET', 'POST'])
def manage_tournaments():
    all_players = PlayerModel.query.all()

    if request.method == 'POST':
        opponents = [
            request.form.get(f'opponent{i}') for i in range(1, 7)
            if request.form.get(f'opponent{i}')
        ]
        selected_players = request.form.getlist('players')

        tournament = TournamentModel(
            date=request.form['date'],
            place=request.form['place'],
            team_name=request.form['team_name'],
            opponents=','.join(opponents),
            players=','.join(selected_players),
            coach_notes=request.form.get('coach_notes', '')
        )
        db.session.add(tournament)
        db.session.commit()
        return redirect('/tournaments?open=form')  # 🔁 keep form open

    open_form = request.args.get('open') == 'form'
    all_tournaments = TournamentModel.query.order_by(TournamentModel.date.desc()).all()
    return render_template('tournaments.html', tournaments=all_tournaments, players=all_players, open_form=open_form)

@app.route('/tournament/<int:tournament_id>/pdf')
def generate_tournament_pdf(tournament_id):
    tournament = TournamentModel.query.get_or_404(tournament_id)
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
 
    # Get matrix entries
    matrix_entries = TournamentMatrixModel.query.filter_by(tournament_id=tournament_id).all()
    matrix_lookup = {
        (entry.player_name.strip(), entry.opponent_name.strip(), entry.period): entry.played
        for entry in matrix_entries
    }

    # Minutes played per player
    from collections import defaultdict
    minutes_played = defaultdict(int)
    for entry in matrix_entries:
        if entry.played:
            minutes_played[entry.player_name.strip()] += 6

    if tournament.coach_notes:
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(x_start, y_start - 40, f"Coach Notes: {tournament.coach_notes[:120]}")

    # Header
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x_start, y_start, f"{tournament.team_name} - Tournament Sheet")
    c.setFont("Helvetica", 10)
    c.drawString(x_start, y_start - 20, f"Date: {tournament.date}     Place: {tournament.place}")

    # Opponent headers
    c.setFont("Helvetica-Bold", 8)
    for i, opponent in enumerate(opponents):
        base_x = x_start + player_col_width + (i * periods_per_opponent * period_col_width)
        block_width = periods_per_opponent * period_col_width
        c.drawCentredString(base_x + block_width / 2, table_top_y, opponent)
        for p in range(periods_per_opponent):
            px = base_x + (p * period_col_width)
            c.drawCentredString(px + period_col_width / 2, table_top_y - 10, f"P{p + 1}")

    # Grid
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

@app.route('/tournament/<int:tournament_id>', methods=['GET', 'POST'])
def tournament_detail(tournament_id):
    tournament = TournamentModel.query.get_or_404(tournament_id)
    players = [p.strip() for p in tournament.players.split(',') if p.strip()]
    opponents = [op.strip() for op in tournament.opponents.split(',') if op.strip()]
    periods = [1, 2, 3, 4]

    if request.method == 'POST':
        # Clear previous matrix entries for this tournament
        TournamentMatrixModel.query.filter_by(tournament_id=tournament_id).delete()

        for opponent in opponents:
            for period in periods:
                for player in players:
                    field_name = f"{opponent}_{period}_{player}".replace(" ", "_")
                    played = request.form.get(field_name) == "on"
                    matrix_entry = TournamentMatrixModel(
                        tournament_id=tournament_id,
                        player_name=player,
                        opponent_name=opponent,
                        period=period,
                        played=played
                    )
                    db.session.add(matrix_entry)

        db.session.commit()
        return redirect(f'/tournament/{tournament_id}')

    # Preload existing matrix data
    existing_matrix = {
        f"{m.opponent_name}_{m.period}_{m.player_name}".replace(" ", "_"): m.played
        for m in TournamentMatrixModel.query.filter_by(tournament_id=tournament_id).all()
    }

    # Stats summary
    from collections import defaultdict
    stats = defaultdict(int)
    for entry in TournamentMatrixModel.query.filter_by(tournament_id=tournament_id).all():
        if entry.played:
            stats[entry.player_name.strip()] += 6  # 6 minutes per period

    return render_template("tournament_detail.html",
                           tournament=tournament,
                           players=players,
                           opponents=opponents,
                           periods=periods,
                           matrix=existing_matrix,
                           stats=stats)

@app.route('/tournament/<int:tournament_id>/export/csv')
def export_tournament_csv(tournament_id):
    tournament = TournamentModel.query.get_or_404(tournament_id)
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

@app.route('/tournament/<int:tournament_id>/edit-notes', methods=['POST'])
def update_coach_notes(tournament_id):
    tournament = TournamentModel.query.get_or_404(tournament_id)
    tournament.coach_notes = request.form.get('coach_notes', '')
    db.session.commit()
    return redirect(f'/tournament/{tournament_id}')

@app.route('/tournament/<int:tournament_id>/edit', methods=['GET', 'POST'])
def edit_tournament(tournament_id):
    tournament = TournamentModel.query.get_or_404(tournament_id)
    all_players = PlayerModel.query.all()

    if request.method == 'POST':
        tournament.date = request.form['date']
        tournament.place = request.form['place']
        tournament.team_name = request.form['team_name']
        tournament.opponents = ','.join([request.form.get(f'opponent{i}') for i in range(1, 7) if request.form.get(f'opponent{i}')])
        tournament.players = ','.join(request.form.getlist('players'))
        tournament.coach_notes = request.form.get('coach_notes', '')
        db.session.commit()
        return redirect(f'/tournament/{tournament_id}')

    current_players = [p.strip() for p in tournament.players.split(',') if p.strip()]
    current_opponents = [o.strip() for o in tournament.opponents.split(',') if o.strip()]

    return render_template('edit_tournament.html',
                           tournament=tournament,
                           all_players=all_players,
                           current_players=current_players,
                           current_opponents=current_opponents)

@app.route('/practice-register', methods=['GET', 'POST'])
def practice_register():
    all_players = PlayerModel.query.all()
    all_exercises = PracticeExerciseModel.query.all()

    if request.method == 'POST':
        date = request.form['date']
        notes = request.form.get('coach_notes', '')
        players_present = ','.join(request.form.getlist('players'))
        exercises_used = ','.join(request.form.getlist('exercises'))
        duration = int(request.form.get('duration_minutes', 0))

        register = PracticeRegisterModel(
            date=date,
            players_present=players_present,
            exercises_used=exercises_used,
            coach_notes=notes,
            duration_minutes=duration
        )
        db.session.add(register)
        db.session.commit()
        return redirect('/practice-register')

    # fetch all exercises once
    exercise_map = {str(e.id): f"{e.category} – {e.execution_description[:40]}..." for e in PracticeExerciseModel.query.all()}

    past_registers = PracticeRegisterModel.query.order_by(PracticeRegisterModel.date.desc()).all()

    # Enrich each register with readable exercises
    for r in past_registers:
        if r.exercises_used:
            r.exercise_labels = [exercise_map.get(eid.strip(), f"ID {eid.strip()}") for eid in r.exercises_used.split(',')]
        else:
            r.exercise_labels = []
    return render_template('practice_register.html',
                           players=all_players,
                           exercises=all_exercises,
                           registers=past_registers)

@app.route('/practice-exercise/<int:exercise_id>/edit', methods=['GET', 'POST'])
def edit_practice_exercise(exercise_id):
    exercise = PracticeExerciseModel.query.get_or_404(exercise_id)

    if request.method == 'POST':
        exercise.category = request.form['category']
        exercise.needed_material = request.form['needed_material']
        exercise.execution_description = request.form['execution_description']
        exercise.image1 = request.form.get('image1')
        exercise.image2 = request.form.get('image2')
        exercise.image3 = request.form.get('image3')
        exercise.image4 = request.form.get('image4')
        db.session.commit()
        return redirect('/practice-exercises')

    return render_template('edit_practice_exercise.html', exercise=exercise)

@app.route('/practice-register/<int:register_id>/edit', methods=['GET', 'POST'])
def edit_practice_register(register_id):
    register = PracticeRegisterModel.query.get_or_404(register_id)
    all_players = PlayerModel.query.all()
    all_exercises = PracticeExerciseModel.query.all()

    if request.method == 'POST':
        register.date = request.form['date']
        register.players_present = ','.join(request.form.getlist('players'))
        register.exercises_used = ','.join(request.form.getlist('exercises'))
        register.coach_notes = request.form.get('coach_notes', '')
        register.duration_minutes = int(request.form.get('duration_minutes', 0))
        db.session.commit()
        return redirect('/practice-register')

    selected_players = register.players_present.split(',') if register.players_present else []
    selected_exercises = register.exercises_used.split(',') if register.exercises_used else []

    return render_template("edit_practice_register.html",
                           register=register,
                           players=all_players,
                           exercises=all_exercises,
                           selected_players=selected_players,
                           selected_exercises=selected_exercises)

@app.route('/dashboard-minutes')
def dashboard_minutes():
    players = PlayerModel.query.order_by(PlayerModel.name).all()
    registers = PracticeRegisterModel.query.all()
    matrix_entries = TournamentMatrixModel.query.filter_by(played=True).all()

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

    return render_template('dashboard_minutes.html',
                           players=players,
                           data=dashboard_data,
                           chart_labels=labels,
                           chart_played=minutes_played,
                           chart_practiced=practice_minutes)

@app.route('/dashboard-totals')
def dashboard_totals():
    players = PlayerModel.query.order_by(PlayerModel.name).all()
    from collections import defaultdict
    totals_data = defaultdict(lambda: {"games_played": 0, "practices_attended": 0})

    # Initialize all players
    for player in players:
        totals_data[player.name]

    matrix_entries = TournamentMatrixModel.query.filter_by(played=True).all()
    seen_games = set()

    for entry in matrix_entries:
        key = (entry.player_name.strip(), entry.tournament_id, entry.opponent_name.strip())
        if key not in seen_games:
            totals_data[entry.player_name.strip()]["games_played"] += 1
            seen_games.add(key)

    practice_registers = PracticeRegisterModel.query.all()
    for reg in practice_registers:
        players_present = [p.strip() for p in reg.players_present.split(',') if p.strip()]
        for p in players_present:
            totals_data[p]["practices_attended"] += 1
    
    # print(totals_data)
    
    return render_template('dashboard_totals.html',
                           players=players,
                           totals_data=totals_data)

@app.route('/export-minutes-csv')
def export_minutes_csv():
    players = PlayerModel.query.order_by(PlayerModel.name).all()
    registers = PracticeRegisterModel.query.all()
    matrix_entries = TournamentMatrixModel.query.filter_by(played=True).all()

    from collections import defaultdict
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

@app.route('/export-totals-csv')
def export_totals_csv():
    players = PlayerModel.query.order_by(PlayerModel.name).all()

    from collections import defaultdict
    totals_data = defaultdict(lambda: {"games_played": 0, "practices_attended": 0})

    matrix_entries = TournamentMatrixModel.query.filter_by(played=True).all()
    seen_games = set()

    for entry in matrix_entries:
        key = (entry.player_name.strip(), entry.tournament_id, entry.opponent_name.strip())
        if key not in seen_games:
            totals_data[entry.player_name.strip()]["games_played"] += 1
            seen_games.add(key)

    practice_registers = PracticeRegisterModel.query.all()
    for reg in practice_registers:
        players_present = [p.strip() for p in reg.players_present.split(',') if p.strip()]
        for p in players_present:
            totals_data[p]["practices_attended"] += 1

    # Prepare CSV
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

@app.route('/edit-player/<int:player_id>', methods=['GET', 'POST'])
def edit_player(player_id):
    player = PlayerModel.query.get_or_404(player_id)

    if request.method == 'POST':
        # Update player fields
        player.season_year = request.form['season_year']
        player.name = request.form['name'].strip()  # Strip spaces automatically!
        player.escalao = request.form['escalao']
        player.n_carteira = request.form['n_carteira']
        player.dob = request.form['dob']
        player.mobile_phone = request.form['mobile_phone']
        player.email = request.form['email']
        db.session.commit()
        return redirect('/players')

    return render_template('edit_player.html', player=player)

if __name__ == '__main__':
    from os import environ
    app.run(host='0.0.0.0', port=int(environ.get('PORT', 5000)))