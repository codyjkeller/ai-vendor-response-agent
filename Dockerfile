# Use an official lightweight Python image.
# 3.11-slim is small, fast, and secure.
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for PDF parsing and SQLite
# (build-essential is for compiling some python libs)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Healthcheck to ensure the container is running
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# The command to run the application
ENTRYPOINT ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
