from flask import Flask
import os
from dotenv import load_dotenv
from .models import UserModel
from .extensions import db, login_manager

def create_app():

    @login_manager.user_loader
    def load_user(user_id):
        return UserModel.query.get(int(user_id))

    load_dotenv()

    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-key")
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # 🧩 Register blueprints INSIDE the function
    from .players.routes import players_bp
    app.register_blueprint(players_bp)

    from .home.routes import home_bp
    app.register_blueprint(home_bp)

    from .auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from .tournaments.routes import tournaments_bp
    app.register_blueprint(tournaments_bp)

    from .practise.routes import practise_bp
    app.register_blueprint(practise_bp)

    from .dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    from .exports.routes import export_bp
    app.register_blueprint(export_bp)

    return app