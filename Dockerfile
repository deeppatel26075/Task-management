FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize the SQLite database using the application factory
RUN python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Using 2 workers for better performance in production
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app:app"]
