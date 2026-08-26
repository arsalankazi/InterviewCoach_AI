# InterviewCoach AI 🤖

> **AI-Powered Mock Interview Platform** — Practice realistic job interviews with a Gemini-powered AI interviewer, get scored feedback, and track your progress over time.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🎤 **Live AI Interview** | Chat with a Gemini-powered AI interviewer in a 4-stage realistic format (Greeting → Introduction → Technical → Adaptive Follow-ups) |
| 🗣️ **Voice I/O** | Web Speech API for voice input + browser TTS for spoken AI responses |
| 📄 **Resume Parsing** | Upload a PDF resume; AI auto-extracts skills and tailors questions to your background |
| 🏷️ **Skills Manager** | View, add, or remove extracted skills from your profile at any time |
| 🎯 **25+ Job Roles** | Covers Generative AI, ML, Data Science, Cloud, DevOps, Software Engineering, QA, Product, and more |
| 📊 **AI Performance Analysis** | Gemini scores each session: Technical Score, Communication Score, Overall Score, Confidence Level |
| 💡 **Question-Level Feedback** | Per-question AI critique, ideal model answers, and topic categorization |
| 📈 **Progress Charts** | Chart.js radar and trend-line charts tracking improvement across sessions |
| 📚 **Weak Topic Tracker** | Aggregates questions scored below 70% across all sessions for targeted improvement |
| 📋 **Interview History** | Full log of all past sessions with scores and direct report links |
| 👥 **Admin Dashboard** | Real-time metrics, searchable student directory, and platform management |
| 🔒 **Secure Auth** | Bcrypt-hashed passwords, session-based auth, role separation, cross-user authorization guards |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, Flask 3.x (Application Factory pattern) |
| **AI Engine** | Google Gemini API (`google-generativeai` SDK) — multi-model fallback |
| **Database** | SQLite 3 via `sqlite3` with per-request connection lifecycle |
| **Resume Parsing** | `pdfplumber` — PDF text extraction + curated skill keyword library |
| **Password Security** | `werkzeug.security` — bcrypt hashing |
| **Frontend** | Vanilla HTML5, CSS3 (dark theme design system ~5300 lines), Vanilla JS |
| **Charts** | Chart.js 4.x — radar, bar, and trend-line charts |
| **Voice** | Web Speech API (SpeechRecognition) + Browser TTS (`speechSynthesis`) |
| **Typography** | Inter (Google Fonts) |
| **Environment** | `python-dotenv` for `.env` configuration management |
| **Testing** | `pytest` + Python `unittest` (50+ integration tests) |

---

## 🚀 Setup & Installation

### Prerequisites
- Python **3.10 or later**
- `pip` package manager
- A **Google Gemini API key** — free at [ai.google.dev](https://ai.google.dev/)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/InterviewCoach_AI.git
cd InterviewCoach_AI
```

### 2. Create & Activate Virtual Environment

```bash
# Create
python -m venv venv

# Activate — Windows PowerShell
.\venv\Scripts\Activate.ps1

# Activate — Windows CMD
.\venv\Scripts\activate.bat

# Activate — Linux / macOS
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Required — your Gemini API key
GEMINI_API_KEY=your_gemini_api_key_here

# Optional — Flask secret key (always change in production!)
SECRET_KEY=your-strong-secret-key-here

# Optional
FLASK_ENV=development
```

### 5. Seed the Admin Account

```bash
# Seed default admin account
flask seed-admin

# Or with custom credentials
flask seed-admin --name "Your Name" --email "admin@yourorg.com" --password "SecurePass@123"
```

Default credentials: `admin@interviewcoach.ai` / `Admin@123456`

### 6. Run the Application

```bash
python run.py
```

App starts at: **`http://127.0.0.1:5000`**

---

## 🔍 Health Check

```http
GET /health
```

```json
{
  "success": true,
  "message": "System is healthy",
  "data": {
    "app_name": "InterviewCoach AI",
    "version": "1.0.0",
    "module": "Module 15 - Final Integration & Testing",
    "status": "healthy",
    "database": "connected"
  }
}
```

---

## 📁 Project Structure

```
Interview_Coach_AI/
│
├── app.py                          # Application factory (create_app)
├── run.py                          # Entry point
├── config.py                       # Multi-environment configuration
├── requirements.txt                # Python dependencies
├── .env                            # Environment variables (not committed)
│
├── database/
│   ├── connection.py               # SQLite per-request lifecycle
│   ├── schema.sql                  # Canonical table definitions
│   ├── schema.py                   # init_db() + safe column migrations
│   └── seed_admin.py               # Admin account seeder CLI
│
├── models/
│   ├── user.py                     # Student model (CRUD, resume, skills)
│   ├── admin.py                    # Admin model
│   ├── interview_session.py        # Interview session lifecycle
│   ├── interview_message.py        # Conversation message turns
│   ├── interview_report.py         # AI analysis report
│   └── question_feedback.py        # Question-level feedback & weak topics
│
├── routes/
│   ├── main_routes.py              # Landing page & /health
│   ├── auth_routes.py              # Student & admin auth
│   ├── student_routes.py           # All student features
│   └── admin_routes.py             # Admin dashboard
│
├── services/
│   ├── gemini_service.py           # Gemini API wrapper (multi-model fallback)
│   ├── conversation_engine.py      # 4-stage interview orchestrator
│   ├── analysis_service.py         # Post-interview AI scoring
│   └── resume_parser.py            # PDF extraction & skill matching
│
├── utils/
│   ├── decorators.py               # @login_required, @admin_required, @guest_required
│   ├── validators.py               # Registration & login validators
│   └── helpers.py                  # api_response() / api_error() helpers
│
├── templates/
│   ├── base.html                   # Global layout, nav, flash messages
│   ├── index.html                  # Public landing page
│   ├── auth/                       # Login, register, admin login
│   ├── student/                    # Dashboard, profile, resume, skills,
│   │                               #   interview setup/room/results/history
│   └── admin/                      # Admin console
│
├── static/
│   ├── css/style.css               # Complete dark-theme design system
│   ├── js/
│   │   ├── main.js                 # Global UI utilities
│   │   └── interview_room.js       # Chat engine, voice I/O, TTS
│   └── uploads/resumes/            # Student resume PDFs
│
└── tests/
    └── test_integration.py         # Module 15 end-to-end test suite (50+ tests)
```

---

## 🗺️ Module Roadmap

| # | Module | Status |
|---|---|---|
| 01 | **Project Foundation** — App factory, blueprints, SQLite lifecycle, config | ✅ |
| 02 | **Authentication & User Profiles** — Registration, login, sessions, password hashing | ✅ |
| 03 | **Admin System** — Admin model, seeder CLI, `@admin_required`, admin portal | ✅ |
| 04 | **Database Schema** — Users, sessions, messages, reports, question_feedback tables | ✅ |
| 05 | **Student Dashboard** — Metrics, quick actions, weak topics, skills overview | ✅ |
| 06 | **Resume Upload & Management** — PDF validation, secure storage, view/download | ✅ |
| 07 | **Skills Manager** — Auto-extraction, add/remove, curated library, custom skills | ✅ |
| 08 | **Interview Setup** — Interviewer persona (gender/name), 25+ job roles, custom roles | ✅ |
| 09 | **AI Conversation Engine** — 4-stage interview, Gemini multi-turn chat, fallback engine | ✅ |
| 10 | **Gemini API Integration** — Multi-model fallback, strict history formatting, error handling | ✅ |
| 11 | **Virtual Interview Room** — Split-screen UI, real-time chat, session state management | ✅ |
| 12 | **Voice I/O** — Web Speech API input, browser TTS output, visual mic indicator | ✅ |
| 13 | **Post-Interview Analysis** — Gemini scoring, JSON parsing, report persistence, fallbacks | ✅ |
| 14 | **Results & Charts** — Score rings, radar chart, progress trend, question feedback, history | ✅ |
| 15 | **Final Integration & Testing** — Bug fixes, landing page, test suite, README | ✅ |

---

## 🖼️ Screenshots

> Add your own screenshots after running the application locally.

| Page | File |
|---|---|
| Landing page | `screenshots/landing.png` |
| Student dashboard | `screenshots/dashboard.png` |
| Live AI interview | `screenshots/interview_room.png` |
| Results & charts | `screenshots/results.png` |
| Admin console | `screenshots/admin.png` |

---

## 🧪 Running Tests

```bash
# Run full integration test suite via pytest
python -m pytest tests/test_integration.py -v

# Or standalone
python tests/test_integration.py
```

**Test coverage includes:**
- Student auth (register, login, logout, invalid inputs, duplicate email)
- Resume upload validation (no file, wrong type, empty file)
- Skills management (add, remove, custom, invalid actions)
- Interview setup validation (missing fields, invalid roles)
- Full session lifecycle (create → room → chat → end → results → history)
- Authorization (cross-user session blocked, admin routes protected, unauthenticated API → 401/403)
- Edge cases (empty states, non-existent sessions, 404 handling)
- Route integrity (all routes return valid HTTP responses, no 500 crashes)

---

## 🔐 Security Notes

- All passwords are bcrypt-hashed via `werkzeug.security`
- Session data never exposes password hashes
- `@login_required` and `@admin_required` decorators guard all protected routes
- Cross-user authorization enforced: students cannot access other students' sessions
- Students cannot access admin routes (redirected to own dashboard)
- Open redirect protection on login `next` parameter
- File uploads validated by extension, MIME type, and size (15MB PDF only)

---

## 🤝 Credits

| Component | Credit |
|---|---|
| **AI Engine** | [Google Gemini API](https://ai.google.dev/) |
| **Web Framework** | [Flask](https://flask.palletsprojects.com/) by Pallets |
| **PDF Parsing** | [pdfplumber](https://github.com/jsvine/pdfplumber) |
| **Charts** | [Chart.js](https://www.chartjs.org/) |
| **Typography** | [Inter](https://fonts.google.com/specimen/Inter) via Google Fonts |
| **Voice API** | W3C Web Speech API + Browser `speechSynthesis` |

---

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.

---

*Built as a competition project demonstrating modular Flask architecture, Gemini AI integration, voice-enabled interviews, and full-stack web development best practices.*
