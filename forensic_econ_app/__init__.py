import os
from flask import Flask
from flask_migrate import Migrate
from .models.models import db
from .config.config import config

migrate = Migrate()

def create_app(config_name=None):
    """Application factory function."""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    from .routes import evaluee, demographics, worklife, aef, earnings
    from forensic_econ_app.routes.healthcare import healthcare
    from forensic_econ_app.routes.settings import settings
    
    app.register_blueprint(evaluee.bp)
    app.register_blueprint(demographics.bp)
    app.register_blueprint(worklife.bp)
    app.register_blueprint(aef.bp)
    app.register_blueprint(earnings.bp)
    app.register_blueprint(healthcare)
    app.register_blueprint(settings)
    
    return app 