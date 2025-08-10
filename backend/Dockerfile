# backend/Dockerfile

FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy only requirements first for caching
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy all backend files
COPY . /app

# Expose port your app runs on (adjust if needed)
EXPOSE 8000

# Start the app using gunicorn (adjust app:app if your main Flask/FastAPI app is named differently)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
