<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.0-black?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/JWT_Auth-Stateless-FF4081?style=for-the-badge&logo=json-web-tokens&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" />
</div>

<h1 align="center">Project PA: Cloud-Based Discipline Intelligence System</h1>

<p align="center">
  <strong>An elite, enterprise-grade, multi-tenant productivity SaaS platform with priority-weighted task scoring, dual token-session authentication, role-based access, automated cron alerting, and advanced analytics.</strong>
</p>

## 🚀 Architectural Vision & Core Upgrades

Generic task apps treat all tasks equally. **Project PA** separates itself by measuring real effort scientifically using a **Discipline Evaluation Engine** that applies priority weighting and status multipliers.

### 🌟 Elite 8–10 LPA System Upgrades
1. **Multi-User / Role-Based Access Control (RBAC)**: Added `user` & `admin` tiers. Administrators can view enterprise-wide engagement, change roles, and assign tasks directly to team members.
2. **Stateless JWT API Layer**: Implemented token-based authentication using `Flask-JWT-Extended` via `/api/v1/auth/`. The core API supports dual authentication (`Bearer` tokens for mobile/REST clients & `Session` auth for the browser dashboard).
3. **Automated Notification Engine**: Background jobs process at 00:01 daily via `APScheduler`, sending real-time `Flask-Mail` alerts:
   - "Streak at Risk" alerts when unfinished high-priority tasks are detected.
   - "Streak broken" alerts.
   - "Personal Best" congratulatory emails for new daily high scores.
4. **API Hardening**: Native cursor pagination (`?page=1&per_page=20`), rate limiting using `Flask-Limiter` (`200 requests/hour` by IP), and API response versioning envelopes.
5. **Robust Test Suite**: Full `pytest` integration including a dedicated fixture setup (`conftest.py`) mocking SMTP mail flows and executing multi-tenant tests.

---

## 🏗️ Technical Architecture & Directory Structure

Project PA follows a modern clean-architecture design pattern completely decoupling the HTTP/presentation layer from core business logic:

```text
project-pa/
├── app.py                  # App factory, extension configuration, error handling
├── models/                 # SQLAlchemy Enterprise Domain Models
│   ├── user.py             # User entities, scrypt auth, roles, bio, preferences
│   └── task.py             # Task schemas, daily task instances, score history
├── routes/                 # Multi-Tenant Blueprint Architecture
│   ├── auth_routes.py      # Browser Session Auth (Login/Register/Logout)
│   ├── jwt_routes.py       # REST API Auth (Login/Refresh/Me/Revoke)
│   ├── admin_routes.py     # Admin Management Panel (Users, Team Assignment)
│   ├── dashboard_routes.py # Dynamic Jinja2 Web Views & Charts
│   └── api_routes.py       # Advanced REST API (Pagination, Filtering, Patch Status)
├── services/               # Isolated Business Logic Layer
│   ├── email_service.py    # Multi-alert email notification engine
│   ├── scheduler.py        # APScheduler nightly cron system
│   └── scoring_service.py  # Discipline Evaluation Engine Core
└── tests/                  # Automated Tests (pytest-cov)
    ├── conftest.py         # App, DB, Admin & user fixtures
    ├── test_api.py         # Complete token-based CRUD API tests
    ├── test_auth.py        # Web login & registration suite
    └── test_admin.py       # Role-based protection tests
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Core Backend** | Python 3.11+, Flask 3.0, Flask-Login |
| **API Tokens** | Flask-JWT-Extended (Stateless authentication) |
| **Alerts & Scheduling**| APScheduler, Flask-Mail (Custom HTML templates) |
| **Traffic Guard** | Flask-Limiter (Token Bucket Rate Limiting) |
| **Storage & ORM** | SQLAlchemy, SQLite (Development), Ready for PostgreSQL |
| **Design System** | Dark Mode Glassmorphism Interface, Chart.js, Google Fonts |
| **CI/CD & DevOps** | GitHub Actions, Docker, Gunicorn, Render (`render.yaml`) |

---

## 🔌 API Reference Documentation

All endpoints return an envelope: `{"success": true, "data": {...}, "api_version": "1.0"}`

### Authentication & Profiles
`POST /api/v1/auth/login` → Get stateless access & refresh tokens  
`POST /api/v1/auth/refresh` → Exchange refresh token for access token  
`GET /api/v1/auth/me` → Access logged-in profile payload  

### Task & Team Management
`GET /api/v1/health` → Pings DB and checks system readiness  
`GET /api/v1/tasks` → Fetch your task board (`?page=1&per_page=20`)  
`POST /api/v1/tasks` → Add a new task (`title`, `priority`, `recurrence`, `category`)  
`PATCH /api/v1/tasks/<id>/status` → Alter task instance status (`Pending` \| `Full` \| `Half` \| `Missed`)  
`GET /api/v1/stats` → Aggregate 30-day moving average, lifetime totals, and tiers  

---

## 💻 Setup & Installation

### 1. Configure the Environment
Create a `.env` file from the provided template:
```bash
cp .env.example .env
```
Update parameters including your SMTP details:
```ini
SECRET_KEY=dev-secret-key-change-in-prod
JWT_SECRET_KEY=jwt-secret-key-change-in-prod
MAIL_USERNAME=deeppatel26075@gmail.com
MAIL_PASSWORD=your_gmail_app_password
```

### 2. Local Execution
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Visit `http://127.0.0.1:5000` to preview the system.

### 3. Run Automated Tests
```bash
pytest tests/ -v --cov=.
```

---
*Developed to showcase highly scalable, production-grade SaaS architecture, REST endpoints, multi-user role management, and test-driven development.*
