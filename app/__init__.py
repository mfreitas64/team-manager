from flask import Flask, request, session, url_for
from flask_login import current_user
from flask_babel import Babel, _
from dotenv import load_dotenv
import os

from .models import UserModel, SeasonModel
from .extensions import db, login_manager

# 🌍 Initialize Babel
babel = Babel()

def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-key")
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 🌐 Babel config
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
    app.config['LANGUAGES'] = ['en', 'pt']

    # 🔐 Login manager
    @login_manager.user_loader
    def load_user(user_id):
        return UserModel.query.get(int(user_id))

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    babel.init_app(app)

    # 🌍 Babel language selector
    @babel.localeselector
    def get_locale():
        lang = request.args.get('lang')
        if lang:
            session['lang'] = lang
        return session.get('lang', 'en')

    # ✅ Inject globals into templates
    app.jinja_env.globals['get_locale'] = get_locale
    app.jinja_env.globals['current_user'] = current_user

    @app.context_processor
    def utility_processor():
        def url_for_lang(lang_code):
            args = request.view_args.copy() if request.view_args else {}
            args.update(request.args.to_dict())
            args['lang'] = lang_code
            return url_for(request.endpoint, **args)
        return dict(url_for_lang=url_for_lang)

    @app.context_processor
    def inject_current_season():
        season_id = session.get('season_id')
        if not season_id or not getattr(current_user, 'is_authenticated', False):
            return dict(current_season=None)

        season = SeasonModel.query.filter_by(id=season_id, user_id=current_user.id).first()
        return dict(current_season=season)

    # 🧩 Register Blueprints (after globals/context are set)
    from .players.routes import players_bp
    from .home.routes import home_bp
    from .auth.routes import auth_bp
    from .tournaments.routes import tournaments_bp
    from .practise.routes import practise_bp
    from .dashboard.routes import dashboard_bp
    from .exports.routes import export_bp
    from .season.routes import season_bp

    app.register_blueprint(players_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tournaments_bp)
    app.register_blueprint(practise_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(season_bp)

    return app