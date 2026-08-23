import os
from pathlib import Path
from dotenv import load_dotenv
import click
from flask import Flask
from config import get_config
import database
from database.schema import init_db
import routes
from utils.helpers import api_error

# Ensure .env is loaded as early as possible
load_dotenv(override=True)
_api_key = os.environ.get('GEMINI_API_KEY')
if _api_key:
    _masked_key = f"{_api_key[:6]}...{_api_key[-4:]}" if len(_api_key) > 10 else f"{_api_key[:3]}..."
    print(f"[App Startup] GEMINI_API_KEY successfully loaded from .env (Key: {_masked_key})")
else:
    print("[App Startup] WARNING: GEMINI_API_KEY is NOT set in environment or .env file.")



def create_app(config_name=None):
    """
    Application factory for InterviewCoach AI.
    
    :param config_name: Environment configuration name ('development', 'testing', 'production')
    :return: Configured Flask application instance
    """
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    # Ensure instance directory exists
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    # Ensure upload directory exists
    upload_folder = Path(app.config.get('UPLOAD_FOLDER', str(instance_path)))
    upload_folder.mkdir(parents=True, exist_ok=True)

    # Initialize SQLite database connection management
    database.init_app(app)

    # Ensure database schema and tables exist
    with app.app_context():
        init_db()

    # Register blueprints / routes
    routes.register_routes(app)

    # Register CLI commands
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize database schema tables."""
        init_db()
        click.echo("Initialized the database tables successfully.")

    @app.cli.command('seed-admin')
    @click.option('--name', default='Super Admin', help='Administrator display name')
    @click.option('--email', default='admin@interviewcoach.ai', help='Administrator email address')
    @click.option('--password', default='Admin@123456', help='Administrator password')
    def seed_admin_command(name, email, password):
        """Seed initial administrator account."""
        from database.seed_admin import seed_admin
        seed_admin(name=name, email=email, password=password)

    # Register global HTTP error handlers
    @app.errorhandler(404)
    def handle_not_found(error):
        return api_error(message="Resource not found", status_code=404)

    @app.errorhandler(500)
    def handle_internal_server_error(error):
        return api_error(message="Internal server error", status_code=500)

    return app


if __name__ == '__main__':
    application = create_app()
    application.run(host='127.0.0.1', port=5000)
