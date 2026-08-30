from datetime import datetime, date
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


def safe_format_date(val, fmt='%Y-%m-%d', fallback=''):
    """
    Safely format a date/datetime object or date string to '%Y-%m-%d'.
    Works seamlessly with both Python datetime objects and ISO strings.
    """
    if not val:
        return fallback
    if isinstance(val, (datetime, date)):
        return val.strftime(fmt)
    if hasattr(val, 'strftime'):
        return val.strftime(fmt)
    val_str = str(val).strip()
    return val_str[:10] if len(val_str) >= 10 else (val_str or fallback)


def safe_format_time(val, fmt='%H:%M', fallback=''):
    """
    Safely format a datetime object or timestamp string to '%H:%M'.
    """
    if not val:
        return fallback
    if isinstance(val, datetime):
        return val.strftime(fmt)
    if hasattr(val, 'strftime'):
        return val.strftime(fmt)
    val_str = str(val).strip()
    return val_str[11:16] if len(val_str) >= 16 else fallback


def safe_format_datetime(val, fmt='%Y-%m-%d %H:%M', fallback=''):
    """
    Safely format a datetime object or timestamp string to '%Y-%m-%d %H:%M'.
    """
    if not val:
        return fallback
    if isinstance(val, (datetime, date)):
        return val.strftime(fmt)
    if hasattr(val, 'strftime'):
        return val.strftime(fmt)
    val_str = str(val).strip()
    return val_str[:16] if len(val_str) >= 16 else (val_str or fallback)

