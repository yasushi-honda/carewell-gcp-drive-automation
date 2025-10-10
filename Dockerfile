FROM python:3.11-bookworm

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers with all dependencies
# Using bookworm (full image) ensures all system dependencies are available
RUN playwright install --with-deps chromium

# Copy application code
COPY src/ ./src/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the function with routing support
CMD ["functions-framework", "--target=app", "--source=src/main.py"]
