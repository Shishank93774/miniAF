FROM python:3.11-slim

WORKDIR /app

# Copy shared code
COPY common /app/common

# Copy scheduler code
COPY scheduler/app /app/scheduler/app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Let Python find common/
ENV PYTHONPATH=/app

CMD ["python", "scheduler/app/main.py"]
