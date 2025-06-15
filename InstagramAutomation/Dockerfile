FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install OS and Python dependencies
RUN apt update && \
    apt install -y \
    python3 python3-pip python3-dev python3-venv \
    build-essential curl git wget unzip xvfb \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 libxrandr2 \
    libxdamage1 libxext6 libxfixes3 libxkbcommon0 libgtk-3-0 libx11-xcb1 libxcb1 \
    libasound2 libdrm2 libgbm1 libxshmfence1 libxss1 fonts-liberation && \
    apt clean && rm -rf /var/lib/apt/lists/*

RUN apt update && apt install xvfb -y

# Upgrade pip and install Python packages
RUN python3 -m pip install --upgrade pip && \
    pip install \
    requests numpy pandas flask matplotlib scikit-learn tqdm beautifulsoup4 \
    boto3 botocore playwright playwright-stealth

# Install Playwright Chromium browser
RUN python3 -m playwright install chromium

# Set working directory
WORKDIR /app

# Copy application files
COPY ./app /app

# Optional: expose port for Flask or debugging
# EXPOSE 5000

# Launch using xvfb-run for headful Chromium (optional)
CMD ["xvfb-run", "-a","python3", "main.py"]
