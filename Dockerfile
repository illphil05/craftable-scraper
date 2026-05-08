FROM python:3.12-slim

# Install Playwright/Chromium dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 fonts-liberation libxshmfence1 libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY app/ ./app/
COPY tailwind.config.js .

# Build Tailwind CSS v3 via standalone CLI (no Node.js required)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 \
       -o /usr/local/bin/tailwindcss \
    && chmod +x /usr/local/bin/tailwindcss \
    && tailwindcss -i ./app/static/input.css -o ./app/static/output.css --minify \
    && rm /usr/local/bin/tailwindcss \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 3010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3010"]
