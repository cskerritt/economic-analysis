import os
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from .models.models import db, User
from .config.config import config

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

def create_app(config_name=None):
    """Application factory function."""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Register blueprints
    from .routes import evaluee, demographics, worklife, aef, earnings
    from forensic_econ_app.routes.healthcare import healthcare
    from forensic_econ_app.routes.settings import settings
    from forensic_econ_app.routes.health import bp as health_bp
    from forensic_econ_app.routes.auth import bp as auth_bp
    from forensic_econ_app.routes.household import household
    from forensic_econ_app.routes.pcpm import bp as pcpm_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(evaluee.bp)
    app.register_blueprint(demographics.bp)
    app.register_blueprint(worklife.bp)
    app.register_blueprint(aef.bp)
    app.register_blueprint(earnings.bp)
    app.register_blueprint(healthcare)
    app.register_blueprint(settings)
    app.register_blueprint(health_bp)
    app.register_blueprint(household)
    app.register_blueprint(pcpm_bp)
    
    return app 