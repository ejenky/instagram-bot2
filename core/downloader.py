"""Media downloader - handles downloading from any social media link."""

import os
import re
import asyncio
import logging
import random
import string

logger = logging.getLogger(__name__)


class MediaDownloader:
    """Downloads media from social media URLs using yt-dlp."""

    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir

    @staticmethod
    def _random_str(length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @staticmethod
    def is_supported_url(url: str) -> bool:
        """Check if a URL looks like a social media link we can download from.

        Uses a broad check - yt-dlp supports thousands of sites, so we accept
        any http/https URL and let yt-dlp figure it out.
        """
        url_lower = url.lower().strip()
        return url_lower.startswith('http://') or url_lower.startswith('https://')

    @staticmethod
    def detect_media_type_from_url(url: str) -> str:
        """Guess if URL points to image or video based on URL patterns."""
        url_lower = url.lower()
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        for ext in image_extensions:
            if ext in url_lower:
                return 'image'
        return 'video'

    async def download(self, url: str) -> dict:
        """Download media from URL. Returns dict with path, type, and info."""
        rand = self._random_str()
        output_template = os.path.join(self.temp_dir, f'input_{rand}.%(ext)s')

        cmd = [
            'yt-dlp',
            '--no-warnings',
            '-f', 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            '--merge-output-format', 'mp4',
            '-o', output_template,
            '--no-playlist',
            '--no-check-certificates',
            '--retries', '3',
            '--fragment-retries', '3',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--extractor-args', 'twitter:api=syndication',
            '--write-thumbnail',
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"yt-dlp failed: {error_msg}")
            raise Exception("Download failed. Check the link is valid and public.")

        # Find the downloaded file
        downloaded_file = None
        thumbnail_file = None
        for f in os.listdir(self.temp_dir):
            if f.startswith(f'input_{rand}'):
                full_path = os.path.join(self.temp_dir, f)
                if any(f.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    thumbnail_file = full_path
                else:
                    downloaded_file = full_path

        if not downloaded_file:
            raise Exception("Downloaded file not found")

        # Detect type
        ext = os.path.splitext(downloaded_file)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            media_type = 'image'
        else:
            media_type = 'video'

        return {
            'path': downloaded_file,
            'type': media_type,
            'thumbnail': thumbnail_file,
        }

    async def download_image(self, url: str) -> str:
        """Download a direct image URL."""
        rand = self._random_str()
        output_path = os.path.join(self.temp_dir, f'input_{rand}.jpg')

        cmd = [
            'curl', '-L', '-o', output_path,
            '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            '--max-time', '30',
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        if process.returncode != 0 or not os.path.exists(output_path):
            raise Exception("Image download failed")

        return output_path
