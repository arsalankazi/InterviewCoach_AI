from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db


class User:
    """
    Student User model managing student profile data, password hashing, and database persistence.
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
        Create and persist a new Student user in the database.
        Returns the created User instance.
        """
        db = get_db()
        email_clean = email.strip().lower()
        password_hash = generate_password_hash(password)

        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?);
            """,
            (name.strip(), email_clean, password_hash)
        )
        db.commit()

        user_id = cursor.lastrowid
        return cls.get_by_id(user_id)

    @classmethod
    def get_by_id(cls, user_id):
        """Retrieve a user by their unique primary key ID."""
        if not user_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_email(cls, email):
        """Retrieve a user by their unique email address."""
        if not email:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE;", (email.strip().lower(),))
        row = cursor.fetchone()
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    def email_exists(cls, email):
        """Check if an email is already registered by a user."""
        return cls.get_by_email(email) is not None

    @classmethod
    def count(cls):
        """Return the total count of registered students."""
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM users;")
        row = cursor.fetchone()
        return row[0] if row else 0

    @classmethod
    def get_all(cls, search=None):
        """
        Retrieve all registered students ordered by registration date descending.
        Optionally filter by name or email substring.
        """
        db = get_db()
        cursor = db.cursor()
        if search and search.strip():
            query_pattern = f"%{search.strip().lower()}%"
            cursor.execute(
                """
                SELECT * FROM users 
                WHERE name LIKE ? OR email LIKE ? 
                ORDER BY created_at DESC;
                """,
                (query_pattern, query_pattern)
            )
        else:
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC;")

        rows = cursor.fetchall()
        return [cls._from_row(row) for row in rows]

    @classmethod
    def _from_row(cls, row):
        """Construct a User instance from a SQLite Row."""
        return cls(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            password_hash=row['password_hash'],
            created_at=row['created_at']
        )

    def to_dict(self):
        """Serialize user object without sensitive password hash."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": str(self.created_at) if self.created_at else None
        }
