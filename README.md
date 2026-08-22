# InterviewCoach AI

An intelligent, modular AI-powered interview preparation platform built with Python and Flask.

---

## 🏗️ Architecture Overview

The project is structured according to clean architecture and separation of concerns:

```
Interview_Coach_AI/
├── config.py                      # Multi-environment configuration management
├── app.py                         # Application factory (create_app)
├── run.py                         # Application entrypoint
├── requirements.txt               # Project dependencies
├── README.md                      # Documentation
├── instance/                      # Instance-specific storage (SQLite DB)
├── database/                      # Database lifecycle and connection management
│   ├── __init__.py
│   └── connection.py              # SQLite connection handlers & teardown hooks
├── models/                        # Data models and database schemas
│   └── __init__.py
├── routes/                        # Modular route blueprints
│   ├── __init__.py
│   └── main_routes.py             # Landing page & healthcheck routes
├── services/                      # Business logic & AI orchestration
│   └── __init__.py
├── utils/                         # Reusable utilities and response formatters
│   ├── __init__.py
│   └── helpers.py
├── static/                        # Frontend static assets (CSS, JS, uploads)
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── main.js
│   ├── images/
│   └── uploads/
│       └── resumes/
└── templates/                     # Jinja2 HTML layout and page templates
    ├── base.html
    └── index.html
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ (Python 3.14 compatible)
- `pip` package manager

### 2. Set Up Virtual Environment

```bash
# Create virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (cmd):
.\venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python run.py
```

The application will start at: `http://127.0.0.1:5000/`

---

## 🔍 Health Check & API Status

A built-in healthcheck route is available to verify application and database connectivity:

```http
GET /health
```

**Response Example:**
```json
{
  "success": true,
  "message": "System is healthy",
  "data": {
    "app_name": "InterviewCoach AI",
    "database": "connected",
    "module": "Module 1 - Project Foundation",
    "status": "healthy",
    "version": "0.1.0"
  }
}
```

---

## 🗺️ Project Modules & Roadmap

- [x] **Module 1: Project Foundation** — App factory, modular architecture, SQLite connection lifecycle, configuration management.
- [ ] **Module 2: Authentication & User Profiles** — User registration, secure login, sessions, and profile management.
- [ ] **Module 3: Resume Processing & Job Role Mapping** — PDF/text parsing and skills extraction.
- [ ] **Module 4: AI Interview Engine** — Dynamic question generation, speech/text response processing, real-time coaching.
- [ ] **Module 5: Feedback & Analytics Dashboard** — Detailed scoring, performance analytics, and improvement suggestions.

---

## 📄 License
Proprietary / MIT (as configured for InterviewCoach AI).
