-- Schema definition for InterviewCoach AI

-- Students / Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    resume_filename TEXT DEFAULT NULL,
    resume_uploaded_at TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Administrators table
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Interview Sessions table
CREATE TABLE IF NOT EXISTS interview_sessions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interviewer_gender TEXT    NOT NULL CHECK(interviewer_gender IN ('male', 'female')),
    interviewer_name   TEXT    NOT NULL,
    job_role           TEXT    NOT NULL,
    status             TEXT    NOT NULL DEFAULT 'setup'
                               CHECK(status IN ('setup', 'in_progress', 'completed')),
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Interview Messages table
CREATE TABLE IF NOT EXISTS interview_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    sender       TEXT    NOT NULL CHECK(sender IN ('ai', 'student')),
    message_text TEXT    NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON interview_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON interview_messages(session_id);
