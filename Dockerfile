FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    fonts-dejavu-core \
    fonts-inter \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Always upgrade yt-dlp to latest version (X/Twitter changes frequently)
RUN pip install --upgrade yt-dlp

COPY core/ core/
COPY editors/ editors/
COPY creators/ creators/
COPY handlers/ handlers/
COPY bot.py .

RUN mkdir -p /app/data /app/assets /app/templates

ENV TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
ENV DEFAULT_WATERMARK=@yourusername
ENV WATERMARK_PATH=/app/assets/watermark.png
ENV DATA_DIR=/app/data

CMD ["python", "bot.py"]
