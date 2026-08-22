import re
from models.user import User
from models.admin import Admin

# RFC 5322 standard email regex pattern
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
)

MIN_PASSWORD_LENGTH = 8


def validate_email_format(email):
    """
    Verify if email has a valid syntax format.
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_registration(name, email, password, confirm_password=None):
    """
    Validate student registration fields.
    Returns (is_valid: bool, error_message: str or None).
    """
    if not name or not name.strip():
        return False, "Full name is required."
    
    if len(name.strip()) < 2:
        return False, "Name must be at least 2 characters long."

    if not email or not email.strip():
        return False, "Email address is required."

    if not validate_email_format(email):
        return False, "Please enter a valid email address."

    if not password:
        return False, "Password is required."

    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."

    if confirm_password is not None and password != confirm_password:
        return False, "Passwords do not match."

    # Check for duplicate email in users table
    if User.email_exists(email):
        return False, "An account with this email already exists."

    return True, None


def validate_login(email, password):
    """
    Validate basic login parameters.
    Returns (is_valid: bool, error_message: str or None).
    """
    if not email or not email.strip():
        return False, "Email address is required."

    if not validate_email_format(email):
        return False, "Please enter a valid email address."

    if not password:
        return False, "Password is required."

    return True, None
