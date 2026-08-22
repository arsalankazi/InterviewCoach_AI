from flask import jsonify


def api_response(success=True, message="", data=None, status_code=200):
    """
    Standardized API response helper.
    """
    payload = {
        "success": success,
        "message": message,
        "data": data if data is not None else {}
    }
    return jsonify(payload), status_code


def api_error(message="An error occurred", status_code=400, details=None):
    """
    Standardized API error response helper.
    """
    payload = {
        "success": False,
        "error": message,
        "details": details if details is not None else {}
    }
    return jsonify(payload), status_code
