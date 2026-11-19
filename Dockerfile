FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Copy requirements first so Docker caches the dependency layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]