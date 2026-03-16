FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    fonts-dejavu-core \
    fonts-inter \
    fonts-liberation \
    fonts-noto \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Always upgrade yt-dlp and gallery-dl to latest version
RUN pip install --upgrade yt-dlp gallery-dl

COPY core/ core/
COPY editors/ editors/
COPY creators/ creators/
COPY handlers/ handlers/
COPY config/ config/
COPY bot.py .

RUN mkdir -p /app/data /app/assets /app/templates \
    /tmp/content-bot/downloads /tmp/content-bot/output \
    /opt/content-bot/sludge-clips /opt/content-bot/music

ENV TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
ENV ELEVENLABS_API_KEY=
ENV OPENAI_API_KEY=
ENV DEFAULT_WATERMARK=@yourusername
ENV WATERMARK_PATH=/app/assets/watermark.png
ENV DATA_DIR=/app/data
ENV DOWNLOAD_DIR=/tmp/content-bot/downloads
ENV OUTPUT_DIR=/tmp/content-bot/output
ENV SLUDGE_CLIPS_DIR=/opt/content-bot/sludge-clips
ENV MUSIC_DIR=/opt/content-bot/music
ENV MAX_FILE_SIZE=50

CMD ["python", "bot.py"]
