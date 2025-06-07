from .auth import auth_bp
from .game import game_bp
from .history import history_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(game_bp)
    app.register_blueprint(history_bp)