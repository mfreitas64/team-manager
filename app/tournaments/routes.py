from flask import Blueprint, render_template, request, redirect
from flask_login import login_required, current_user
from app.models import TournamentModel, TournamentMatrixModel, PlayerModel
from app.extensions import db
from flask import url_for

tournaments_bp = Blueprint('tournaments', __name__, url_prefix='/tournament')

@tournaments_bp.route('/tournaments', methods=['GET', 'POST'])
@login_required
def manage_tournaments():

    all_players = PlayerModel.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        opponents = [
            request.form.get(f'opponent{i}') for i in range(1, 7)
            if request.form.get(f'opponent{i}')
        ]
        selected_players = request.form.getlist('players')

        tournament = TournamentModel(
            user_id=current_user.id,
            date=request.form['date'],
            place=request.form['place'],
            team_name=request.form['team_name'],
            opponents=','.join(opponents),
            players=','.join(selected_players),
            coach_notes=request.form.get('coach_notes', '')
        )
        db.session.add(tournament)
        db.session.commit()
        return redirect(url_for('tournaments.manage_tournaments', open='form'))

    open_form = request.args.get('open') == 'form'
    all_tournaments = TournamentModel.query.filter_by(user_id=current_user.id).order_by(TournamentModel.date.desc()).all()
    return render_template('tournaments.html', tournaments=all_tournaments, players=all_players, open_form=open_form)

@tournaments_bp.route('/<int:tournament_id>', methods=['GET', 'POST'])
@login_required
def tournament_detail(tournament_id):

    tournament = TournamentModel.query.get_or_404(tournament_id)

    if tournament.user_id != current_user.id:
        return "⛔ Unauthorized", 403
    
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

@tournaments_bp.route('/edit/<int:tournament_id>', methods=['GET', 'POST'])
@login_required
def edit_tournament(tournament_id):

    tournament = TournamentModel.query.get_or_404(tournament_id)

    if tournament.user_id != current_user.id:
        return "⛔ Unauthorized", 403

    all_players = PlayerModel.query.filter_by(user_id=current_user.id).all()

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

@tournaments_bp.route('/<int:tournament_id>/edit-notes', methods=['POST'])
@login_required
def update_coach_notes(tournament_id):
    tournament = TournamentModel.query.get_or_404(tournament_id)

    if tournament.user_id != current_user.id:
        return "⛔ Unauthorized", 403
    
    tournament.coach_notes = request.form.get('coach_notes', '')
    db.session.commit()
    return redirect(url_for('tournaments.tournament_detail', tournament_id=tournament_id))