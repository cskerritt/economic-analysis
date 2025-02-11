import os
from dotenv import load_dotenv

load_dotenv()

# Production Configuration
SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-super-secret-key-change-this'
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Security settings
SESSION_COOKIE_SECURE = True
REMEMBER_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_HTTPONLY = True

# Cache configuration
CACHE_TYPE = 'redis'
CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CACHE_DEFAULT_TIMEOUT = 300

# File upload settings
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# Logging configuration
LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
if LOG_TO_STDOUT:
    import logging
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    app.logger.addHandler(stream_handler)

# Rate limiting
RATELIMIT_ENABLED = True
RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0') 