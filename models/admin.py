from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db


class Admin:
    """
    Administrator model managing system admin credentials and authorization.
    Admin accounts cannot be registered publicly.
    """

    def __init__(self, id=None, name=None, email=None, password_hash=None, created_at=None):
        self.id = id
        self.name = name
        self.email = email.lower() if email else None
        self.password_hash = password_hash
        self.created_at = created_at

    def set_password(self, password):
        """Generate and store password hash using Werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the password against stored password hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @classmethod
    def create(cls, name, email, password):
        """
        Create and persist a new Administrator in the database.
        Returns the created Admin instance.
        """
        db = get_db()
        email_clean = email.strip().lower()
        password_hash = generate_password_hash(password)

        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO admins (name, email, password_hash)
            VALUES (?, ?, ?);
            """,
            (name.strip(), email_clean, password_hash)
        )
        db.commit()

        admin_id = cursor.lastrowid
        return cls.get_by_id(admin_id)

    @classmethod
    def get_by_id(cls, admin_id):
        """Retrieve an admin by their unique primary key ID."""
        if not admin_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM admins WHERE id = ?;", (admin_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_email(cls, email):
        """Retrieve an admin by their unique email address."""
        if not email:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM admins WHERE email = ? COLLATE NOCASE;", (email.strip().lower(),))
        row = cursor.fetchone()
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    def email_exists(cls, email):
        """Check if an email is already registered by an admin."""
        return cls.get_by_email(email) is not None

    @classmethod
    def _from_row(cls, row):
        """Construct an Admin instance from a SQLite Row."""
        return cls(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            password_hash=row['password_hash'],
            created_at=row['created_at']
        )

    def to_dict(self):
        """Serialize admin object without sensitive password hash."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": "admin",
            "created_at": str(self.created_at) if self.created_at else None
        }
