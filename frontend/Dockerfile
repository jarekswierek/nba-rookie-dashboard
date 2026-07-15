FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.4

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

COPY shared/ ./shared/
COPY frontend/ ./frontend/

# Streamlit runs the script with the script's directory on sys.path;
# adding /app lets `from frontend.views.sidebar import ...` and
# `from shared.schemas.draft import ...` resolve instead of blowing
# up with ModuleNotFoundError.
ENV PYTHONPATH=/app

EXPOSE 8501

CMD ["streamlit", "run", "frontend/app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true"]
