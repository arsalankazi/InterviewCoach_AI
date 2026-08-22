import os
from pathlib import Path
from flask import Flask
from config import get_config
import database
import routes
from utils.helpers import api_error


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

    # Register blueprints / routes
    routes.register_routes(app)

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
