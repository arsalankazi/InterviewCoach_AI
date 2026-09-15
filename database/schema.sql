-- Schema definition for PrepVance AI

-- Students / Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    resume_filename TEXT DEFAULT NULL,
    resume_uploaded_at TIMESTAMP DEFAULT NULL,
    extracted_skills TEXT DEFAULT NULL,
    onboarding_completed INTEGER NOT NULL DEFAULT 0,
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
    session_type       TEXT    DEFAULT 'full_interview' NOT NULL,
    interview_type     TEXT    DEFAULT 'mixed' NOT NULL
                               CHECK(interview_type IN ('technical', 'general', 'mixed')),
    total_questions    INTEGER DEFAULT 8 NOT NULL
                               CHECK(total_questions >= 3 AND total_questions <= 20),
    difficulty_level   TEXT    NOT NULL DEFAULT 'medium'
                               CHECK(difficulty_level IN ('easy', 'medium', 'hard', 'adaptive')),
    avatar_mode        TEXT    NOT NULL DEFAULT 'general'
                               CHECK(avatar_mode IN ('general', 'faculty')),
    faculty_avatar     TEXT    DEFAULT NULL
                               CHECK(faculty_avatar IS NULL OR faculty_avatar IN ('director', 'hod')),
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

-- Interview Reports table
CREATE TABLE IF NOT EXISTS interview_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    technical_score     INTEGER NOT NULL DEFAULT 0,
    communication_score INTEGER NOT NULL DEFAULT 0,
    overall_score       INTEGER NOT NULL DEFAULT 0,
    confidence_level    TEXT    NOT NULL DEFAULT 'Moderate',
    strengths           TEXT    NOT NULL DEFAULT '[]',
    weaknesses          TEXT    NOT NULL DEFAULT '[]',
    suggestions         TEXT    NOT NULL DEFAULT '[]',
    analysis_available  INTEGER NOT NULL DEFAULT 1,
    introduction_feedback TEXT    DEFAULT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Question Feedback & Weak Topics table
CREATE TABLE IF NOT EXISTS question_feedback (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    question_text  TEXT    NOT NULL,
    student_answer TEXT    NOT NULL,
    ideal_answer   TEXT    NOT NULL,
    feedback_text  TEXT    NOT NULL,
    topic          TEXT    NOT NULL,
    score          INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON interview_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_type ON interview_sessions(session_type);
CREATE INDEX IF NOT EXISTS idx_messages_session ON interview_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_session ON interview_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_qfeedback_session ON question_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_qfeedback_topic ON question_feedback(topic);
