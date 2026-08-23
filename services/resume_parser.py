"""
services/resume_parser.py

PDF text extraction and skill detection service for InterviewCoach AI.
Uses pdfplumber for text extraction and whole-word regex matching to identify
skills from a curated library. Zero Flask dependency — fully testable in isolation.
"""

import re
import pdfplumber


# ---------------------------------------------------------------------------
# Skill Library — single source of truth for both extraction and the UI dropdown
# ---------------------------------------------------------------------------

SKILL_LIBRARY = [
    # ── Programming Languages ──────────────────────────────────────────────
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C", "R",
    "Go", "Rust", "Scala", "MATLAB", "PHP", "Swift", "Kotlin", "Ruby",
    "Perl", "Shell Scripting", "Bash",

    # ── Databases & Query Languages ────────────────────────────────────────
    "SQL", "MySQL", "PostgreSQL", "SQLite", "MongoDB", "Redis",
    "Oracle", "Microsoft SQL Server", "Cassandra", "Elasticsearch",
    "DynamoDB", "Firebase",

    # ── Data Science & Machine Learning ────────────────────────────────────
    "Pandas", "NumPy", "Matplotlib", "Seaborn", "Plotly",
    "Scikit-learn", "TensorFlow", "PyTorch", "Keras", "OpenCV",
    "NLTK", "SpaCy", "XGBoost", "LightGBM", "Hugging Face",
    "Machine Learning", "Deep Learning", "Natural Language Processing",
    "Computer Vision", "Reinforcement Learning",

    # ── Big Data & Cloud ───────────────────────────────────────────────────
    "Apache Spark", "Hadoop", "Hive", "Kafka", "Airflow",
    "AWS", "Azure", "GCP", "Google Cloud",

    # ── Business Intelligence & Visualization ─────────────────────────────
    "Power BI", "Tableau", "Looker", "Google Data Studio",
    "Excel", "Google Sheets", "Qlik",

    # ── Web & API Development ─────────────────────────────────────────────
    "HTML", "CSS", "React", "Angular", "Vue", "Node.js", "Flask",
    "Django", "FastAPI", "REST API", "GraphQL", "Spring Boot",

    # ── DevOps & Tools ────────────────────────────────────────────────────
    "Git", "Docker", "Kubernetes", "Linux", "Jenkins", "CI/CD",
    "Terraform", "Ansible", "Prometheus",

    # ── Analytics & Methodology ───────────────────────────────────────────
    "Data Analysis", "Data Visualization", "Statistical Analysis",
    "ETL", "Data Wrangling", "Data Cleaning", "Feature Engineering",
    "A/B Testing", "Hypothesis Testing", "Regression Analysis",
    "Time Series Analysis", "Forecasting", "Business Intelligence",
    "Data Modeling", "Data Pipeline",

    # ── Soft Skills ───────────────────────────────────────────────────────
    "Communication", "Leadership", "Teamwork", "Problem Solving",
    "Critical Thinking", "Time Management", "Presentation",
    "Collaboration", "Adaptability", "Project Management",
    "Agile", "Scrum",
]


def _build_pattern(skill: str) -> re.Pattern:
    """
    Build a compiled whole-word regex pattern for a skill name.
    Handles special characters in skill names (C++, Node.js, etc.)
    so they are matched literally, with word-boundary anchors where possible.

    For skills containing non-alphanumeric characters (e.g. C++, REST API),
    we use a lookahead/lookbehind approach instead of \\b to avoid issues
    with non-word boundary characters at skill edges.
    """
    escaped = re.escape(skill)

    # Determine if the skill starts/ends with a word character
    starts_word = bool(re.match(r'\w', skill[0]))
    ends_word = bool(re.match(r'\w', skill[-1]))

    prefix = r'\b' if starts_word else r'(?<!\w)'
    suffix = r'\b' if ends_word else r'(?!\w)'

    return re.compile(f'{prefix}{escaped}{suffix}', re.IGNORECASE)


# Pre-compile all patterns once at module load for performance
_SKILL_PATTERNS: list[tuple[str, re.Pattern]] = [
    (skill, _build_pattern(skill)) for skill in SKILL_LIBRARY
]


def extract_skills_from_pdf(pdf_path: str) -> dict:
    """
    Extract text from a PDF file and match it against the SKILL_LIBRARY.

    Args:
        pdf_path: Absolute path to the PDF file on disk.

    Returns:
        A dict with the following keys:
            - skills (list[str])   : Matched skill names found in the resume.
            - extraction_failed (bool): True when pdfplumber could read the
                                        file but yielded no extractable text
                                        (e.g. scanned image PDF).
            - raw_char_count (int) : Number of characters extracted from PDF.
            - error (str | None)   : Non-None when an unexpected exception
                                     occurred (e.g. corrupt/unreadable PDF).
    """
    result = {
        "skills": [],
        "extraction_failed": False,
        "raw_char_count": 0,
        "error": None,
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

            full_text = "\n".join(pages_text)
            result["raw_char_count"] = len(full_text)

            if not full_text.strip():
                # PDF opened successfully but no text layer was found —
                # most likely a scanned/image PDF.
                result["extraction_failed"] = True
                return result

            # Match skills using pre-compiled whole-word patterns
            matched = []
            for skill, pattern in _SKILL_PATTERNS:
                if pattern.search(full_text):
                    matched.append(skill)

            result["skills"] = matched

    except FileNotFoundError:
        result["extraction_failed"] = True
        result["error"] = f"Resume file not found at path: {pdf_path}"
    except Exception as exc:  # noqa: BLE001
        result["extraction_failed"] = True
        result["error"] = str(exc)

    return result
