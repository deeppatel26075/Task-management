<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.0-black?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" />
</div>

<h1 align="center">Project PA: Discipline Intelligence System</h1>

<p align="center">
  <strong>A premium, production-ready SaaS application for tracking daily discipline, computing weighted effort scores, and visualising long-term consistency.</strong>
</p>

## 🚀 The Problem & Solution

Generic to-do lists treat "Reply to email" and "Deep work session" as equal. **Project PA** fixes this by introducing a **Discipline Evaluation Engine** that applies priority weighting and status multipliers to your daily tasks.

It forces you to confront the reality of your effort:
- Did you just tick off easy tasks? (Low score)
- Did you tackle the hard things? (High score, Streak active)

## 🔥 Core Features

*   **Discipline Evaluation Engine**: Algorithm that computes daily scores (High=20pts, Med=10pts, Low=5pts) with multipliers (Full=1.0x, Half=0.5x, Missed=-1.0x).
*   **Streak & Tier System**: Maintains streaks *only* if all high-priority tasks are completed. Promotes users through tiers (Beginner → Consistent → Elite).
*   **Advanced Analytics Dashboard**: 30-day heatmaps, moving averages, and priority breakdowns using Chart.js.
*   **RESTful JSON API**: Full CRUD API for integrations and external clients.
*   **Premium UI/UX**: Dark mode glassmorphism interface, fully responsive.

## 🏗️ Clean Architecture

The application is structured using a professional, modular factory pattern:

```text
project-pa/
├── app.py                  # Application factory (create_app)
├── models/                 # SQLAlchemy Domain Models
│   ├── user.py             # Auth & Tier logic
│   └── task.py             # Tasks, Instances, Scores
├── routes/                 # Flask Blueprints
│   ├── auth_routes.py      # Authentication
│   ├── dashboard_routes.py # Jinja2 Page Views
│   └── api_routes.py       # REST JSON Endpoints
└── services/
    └── scoring_service.py  # Discipline Evaluation Engine (Business Logic)
```

## 🛠️ Tech Stack

| Category | Technology |
|---|---|
| **Backend** | Python 3.11, Flask, Flask-Login |
| **Database** | SQLAlchemy, SQLite (Ready for PostgreSQL) |
| **Frontend** | Vanilla CSS (Custom Design System), Chart.js |
| **DevOps** | Docker, Gunicorn, GitHub Actions |
| **Hosting** | Render (Docker Environment) |

## 🔌 REST API Documentation

Base URL: `/api/v1` (Requires Session Auth)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/tasks` | List all tasks |
| `POST`| `/tasks` | Create new task (`title`, `priority`) |
| `PUT` | `/tasks/<id>` | Update a task |
| `DELETE`| `/tasks/<id>` | Delete task and history |
| `GET` | `/scores` | Get daily score history |
| `GET` | `/stats` | Aggregate metrics (heatmap, average, tiers) |

## 💻 Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/deeppatel26075/Task-management.git
   cd Task-management
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```
   *The app will be available at `http://127.0.0.1:5000`*

## 🐳 Docker Support

Run instantly using Docker:
```bash
docker build -t project-pa .
docker run -p 5000:5000 project-pa
```

---
*Built as a demonstration of clean architecture, full-stack capability, and production-minded engineering.*
