from .extensions import db
from flask_login import UserMixin

# Database model
class PlayerModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'), nullable=False)
    season_year = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    escalao = db.Column(db.String(50), nullable=False)
    n_carteira = db.Column(db.String(50), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    mobile_phone = db.Column(db.String(20))
    email = db.Column(db.String(100))

class PracticeExerciseModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'))
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
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'))
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
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'))
    date = db.Column(db.String(20), nullable=False)
    players_present = db.Column(db.Text)  # comma-separated player names
    exercises_used = db.Column(db.Text)   # comma-separated exercise IDs
    coach_notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)

class UserModel(db.Model, UserMixin):
    __tablename__ = 'user_model'  # Add this line!

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(512), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)