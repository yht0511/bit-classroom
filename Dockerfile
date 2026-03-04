FROM python:3.9-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies. 
# Note: If bit_login is not on PyPI, you must COPY it into the image manually or provide it as a wheel.
# Assuming here it is installable or present.
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 16201

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "16201"]
