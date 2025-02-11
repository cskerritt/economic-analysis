from flask import Blueprint

bp = Blueprint('health', __name__)

@bp.route('/health')
def health_check():
    """Health check endpoint."""
    return 'healthy', 200 