import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv(override=True)

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent


def _get_database_uri(default_sqlite_path):
    """Resolve database URI from DATABASE_URL environment variable or fallback to SQLite."""
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.strip():
        # SQLAlchemy requires postgresql:// instead of postgres://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url.strip()
    return f"sqlite:///{default_sqlite_path}"


class Config:
    """Base configuration class with default settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-secret-key-change-in-production')
    INSTANCE_PATH = BASE_DIR / 'instance'
    DATABASE_PATH = os.environ.get('DATABASE_PATH', str(BASE_DIR / 'instance' / 'interview_coach.db'))
    SQLALCHEMY_DATABASE_URI = _get_database_uri(DATABASE_PATH)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / 'static' / 'uploads' / 'resumes'))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing environment configuration."""
    DEBUG = True
    TESTING = True
    DATABASE_PATH = ':memory:'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    # Ensure a secure secret key is provided in production
    SECRET_KEY = os.environ.get('SECRET_KEY')


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Retrieve configuration object by environment name."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(config_name, DevelopmentConfig)

