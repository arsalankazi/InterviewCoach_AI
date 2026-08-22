from routes.main_routes import main_bp


def register_routes(app):
    """
    Register all application blueprints with the Flask app instance.
    """
    app.register_blueprint(main_bp)
