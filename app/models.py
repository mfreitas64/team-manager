from .extensions import db
from flask_login import UserMixin
from datetime import datetime, timezone
from sqlalchemy import Date

# Database model
class PlayerModel(db.Model):
    __tablename__ = 'player_model'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey('season_model.id'), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.Date)
    mobile_phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    escalao = db.Column(db.String(50))
    n_carteira = db.Column(db.String(50))

    season = db.relationship('SeasonModel', backref='players')

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
    season_id = db.Column(db.Integer, db.ForeignKey('season_model.id'), nullable=False)
    season = db.relationship('SeasonModel', backref='practice_exercises')

class TournamentModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'))
    date = db.Column(db.String(20), nullable=False)
    place = db.Column(db.String(100), nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    opponents = db.Column(db.Text)  # comma-separated opponent names
    players = db.Column(db.Text)    # comma-separated player names
    coach_notes = db.Column(db.Text)  # Add this line
    season_id = db.Column(db.Integer, db.ForeignKey('season_model.id'), nullable=False)
    season = db.relationship('SeasonModel', backref='tournaments')

class TournamentMatrixModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'), nullable=False) 
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament_model.id'), nullable=False)
    player_name = db.Column(db.String(100), nullable=False)
    opponent_name = db.Column(db.String(100), nullable=False)
    period = db.Column(db.Integer, nullable=False)  # 1 to 4
    played = db.Column(db.Boolean, default=False)
    season_id = db.Column(db.Integer, db.ForeignKey('season_model.id'), nullable=False)
    season = db.relationship('SeasonModel', backref='matrix_entries')

class PracticeRegisterModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'))
    date = db.Column(Date, nullable=False)
    players_present = db.Column(db.Text)  # comma-separated player names
    exercises_used = db.Column(db.Text)   # comma-separated exercise IDs
    coach_notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)
    season_id = db.Column(db.Integer, db.ForeignKey('season_model.id'), nullable=False)
    season = db.relationship('SeasonModel', backref='practice_registers')

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
    
class SeasonModel(db.Model):
    __tablename__ = 'season_model'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # e.g., "2024/2025"
    year = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('UserModel', backref='seasons')

class PlayerSeasonStatsModel(db.Model):
    __tablename__ = 'player_season_stats'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player_model.id'), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey('season_model.id'), nullable=False)

    behavior = db.Column(db.Text)
    technical_skills = db.Column(db.Text)
    team_relation = db.Column(db.Text)
    improvement_areas = db.Column(db.Text)
    height_cm = db.Column(db.Integer)
    weight_kg = db.Column(db.Integer)

    player = db.relationship('PlayerModel', backref='season_stats')
    season = db.relationship('SeasonModel', backref='player_stats')