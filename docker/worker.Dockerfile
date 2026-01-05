FROM python:3.11-slim

WORKDIR /app

COPY common /app/common
COPY worker/app /app

RUN pip install fastapi uvicorn sqlalchemy psycopg[binary]

ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
