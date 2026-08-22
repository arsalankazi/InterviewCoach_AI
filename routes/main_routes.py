from flask import Blueprint, render_template, current_app
from database.connection import get_db
from utils.helpers import api_response, api_error

main_bp = Blueprint('main', __name__)


@main_bp.route('/', methods=['GET'])
def index():
    """Landing page indicating system status and foundation readiness."""
    env = current_app.config.get('ENV', 'development')
    debug_mode = current_app.config.get('DEBUG', False)
    return render_template('index.html', env=env, debug_mode=debug_mode)


@main_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint verifying application and database connectivity.
    """
    db_status = "unknown"
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        if result and result[0] == 1:
            db_status = "connected"
        else:
            db_status = "query_failed"
    except Exception as e:
        db_status = f"error: {str(e)}"

    is_healthy = db_status == "connected"
    data = {
        "status": "healthy" if is_healthy else "degraded",
        "app_name": "InterviewCoach AI",
        "version": "0.1.0",
        "module": "Module 1 - Project Foundation",
        "database": db_status
    }
    
    if is_healthy:
        return api_response(success=True, message="System is healthy", data=data, status_code=200)
    else:
        return api_error(message="System is degraded", status_code=503, details=data)
