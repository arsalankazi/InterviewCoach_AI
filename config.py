import os
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Base configuration class with default settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-secret-key-change-in-production')
    INSTANCE_PATH = BASE_DIR / 'instance'
    DATABASE_PATH = os.environ.get('DATABASE_PATH', str(BASE_DIR / 'instance' / 'interview_coach.db'))
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
