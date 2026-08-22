from routes.main_routes import main_bp
from routes.auth_routes import auth_bp
from routes.student_routes import student_bp
from routes.admin_routes import admin_bp


def register_routes(app):
    """
    Register all application blueprints with the Flask app instance.
    """
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
