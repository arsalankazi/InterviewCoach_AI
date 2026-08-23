import json
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db


class User:
    """
    Student User model managing student profile data, resume tracking,
    skill extraction results, password hashing, and database persistence.
    """

    def __init__(
        self,
        id=None,
        name=None,
        email=None,
        password_hash=None,
        created_at=None,
        resume_filename=None,
        resume_uploaded_at=None,
        extracted_skills=None
    ):
        self.id = id
        self.name = name
        self.email = email.lower() if email else None
        self.password_hash = password_hash
        self.created_at = created_at
        self.resume_filename = resume_filename
        self.resume_uploaded_at = resume_uploaded_at
        # Always stored as a Python list; never None externally
        self.extracted_skills = extracted_skills if isinstance(extracted_skills, list) else []

    def set_password(self, password):
        """Generate and store password hash using Werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the password against stored password hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_resume(self):
        """Check whether the student has an active uploaded resume."""
        return bool(self.resume_filename)

    def get_skills(self) -> list:
        """Return the student's extracted/saved skills as a Python list (never None)."""
        return self.extracted_skills if self.extracted_skills else []

    def save_skills(self, skills_list: list) -> None:
        """
        Persist the given skills list to the database as a JSON string.
        Also updates self.extracted_skills in-memory.
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE users SET extracted_skills = ? WHERE id = ?;",
            (json.dumps(skills_list), self.id)
        )
        db.commit()
        self.extracted_skills = skills_list

    def update_resume(self, filename):
        """
        Update the resume filename and set uploaded_at timestamp to current time.
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            UPDATE users 
            SET resume_filename = ?, resume_uploaded_at = CURRENT_TIMESTAMP 
            WHERE id = ?;
            """,
            (filename, self.id)
        )
        db.commit()

        # Reload updated attributes
        refreshed = self.get_by_id(self.id)
        if refreshed:
            self.resume_filename = refreshed.resume_filename
            self.resume_uploaded_at = refreshed.resume_uploaded_at

    def delete_resume(self, upload_folder=None):
        """
        Delete the physical resume file from disk and clear resume columns in SQLite.
        """
        if self.resume_filename and upload_folder:
            file_path = Path(upload_folder) / self.resume_filename
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            UPDATE users 
            SET resume_filename = NULL, resume_uploaded_at = NULL 
            WHERE id = ?;
            """,
            (self.id,)
        )
        db.commit()
        self.resume_filename = None
        self.resume_uploaded_at = None

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
        keys = row.keys() if hasattr(row, 'keys') else []

        # Deserialize extracted_skills from JSON string to Python list
        raw_skills = row['extracted_skills'] if 'extracted_skills' in keys else None
        if raw_skills:
            try:
                skills = json.loads(raw_skills)
                skills = skills if isinstance(skills, list) else []
            except (json.JSONDecodeError, TypeError):
                skills = []
        else:
            skills = []

        return cls(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            password_hash=row['password_hash'],
            created_at=row['created_at'],
            resume_filename=row['resume_filename'] if 'resume_filename' in keys else None,
            resume_uploaded_at=row['resume_uploaded_at'] if 'resume_uploaded_at' in keys else None,
            extracted_skills=skills
        )

    def to_dict(self):
        """Serialize user object without sensitive password hash."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "has_resume": self.has_resume(),
            "resume_filename": self.resume_filename,
            "resume_uploaded_at": str(self.resume_uploaded_at) if self.resume_uploaded_at else None,
            "extracted_skills": self.get_skills(),
            "created_at": str(self.created_at) if self.created_at else None
        }
