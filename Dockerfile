FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Gunicorn with APScheduler: preload so scheduler starts once
ENV PORT=8080
EXPOSE 8080

CMD exec gunicorn -c gunicorn.conf.py "app:app"
