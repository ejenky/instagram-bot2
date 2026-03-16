"""Media downloader - handles downloading from any social media link.

Supports yt-dlp for videos and gallery-dl for images/galleries.
Also supports profile scraping for batch downloads.
"""

import os
import re
import asyncio
import logging
import random
import string
import glob as globlib

from core.config import DOWNLOAD_TIMEOUT, PROFILE_URL_PATTERNS

logger = logging.getLogger(__name__)


class MediaDownloader:
    """Downloads media from social media URLs using yt-dlp and gallery-dl."""

    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir

    @staticmethod
    def _random_str(length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @staticmethod
    def is_supported_url(url: str) -> bool:
        """Check if a URL looks like a social media link we can download from."""
        url_lower = url.lower().strip()
        return url_lower.startswith('http://') or url_lower.startswith('https://')

    @staticmethod
    def is_profile_url(url: str) -> bool:
        """Check if URL points to a profile page (not a specific post)."""
        for pattern in PROFILE_URL_PATTERNS:
            if re.search(pattern, url):
                return True
        return False

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
        """Download media from URL. Returns dict with path, type, and info.

        Tries yt-dlp first, falls back to gallery-dl for images/galleries.
        """
        rand = self._random_str()

        # Try yt-dlp first
        try:
            result = await self._download_ytdlp(url, rand)
            if result:
                return result
        except Exception as e:
            logger.info(f"yt-dlp failed, trying gallery-dl: {e}")

        # Fallback to gallery-dl
        try:
            result = await self._download_gallery_dl(url, rand)
            if result:
                return result
        except Exception as e:
            logger.error(f"gallery-dl also failed: {e}")

        raise Exception("Download failed. Check the link is valid and public.")

    async def _download_ytdlp(self, url: str, rand: str) -> dict:
        """Download using yt-dlp."""
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

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=DOWNLOAD_TIMEOUT
            )
        except asyncio.TimeoutError:
            process.kill()
            raise Exception("Download timed out")

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"yt-dlp failed: {error_msg}")
            raise Exception("yt-dlp download failed")

        return self._find_downloaded_file(rand)

    async def _download_gallery_dl(self, url: str, rand: str) -> dict:
        """Download using gallery-dl (for images/galleries)."""
        output_dir = os.path.join(self.temp_dir, f'gallery_{rand}')
        os.makedirs(output_dir, exist_ok=True)

        cmd = [
            'gallery-dl',
            '--dest', output_dir,
            '--no-mtime',
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=DOWNLOAD_TIMEOUT
            )
        except asyncio.TimeoutError:
            process.kill()
            raise Exception("Gallery download timed out")

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"gallery-dl failed: {error_msg}")
            raise Exception("gallery-dl download failed")

        # Find downloaded files
        files = []
        for root, _, filenames in os.walk(output_dir):
            for fname in filenames:
                files.append(os.path.join(root, fname))

        if not files:
            raise Exception("No files downloaded by gallery-dl")

        # If single file, return it directly
        if len(files) == 1:
            path = files[0]
            ext = os.path.splitext(path)[1].lower()
            media_type = 'image' if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'] else 'video'
            return {'path': path, 'type': media_type, 'thumbnail': None}

        # Multiple files (gallery) - return as gallery
        return {
            'path': files[0],
            'type': 'gallery',
            'files': files,
            'thumbnail': None,
        }

    async def download_profile(self, url: str, max_items: int = 20) -> list:
        """Download recent posts from a profile URL.

        Returns list of dicts with path and type.
        """
        rand = self._random_str()
        output_dir = os.path.join(self.temp_dir, f'profile_{rand}')
        os.makedirs(output_dir, exist_ok=True)

        results = []

        # Try yt-dlp for video content
        try:
            result = await self._scrape_profile_ytdlp(url, output_dir, max_items)
            results.extend(result)
        except Exception as e:
            logger.info(f"yt-dlp profile scrape failed: {e}")

        # Try gallery-dl for image content
        try:
            result = await self._scrape_profile_gallery_dl(url, output_dir, max_items)
            results.extend(result)
        except Exception as e:
            logger.info(f"gallery-dl profile scrape failed: {e}")

        if not results:
            raise Exception("Could not scrape any content from this profile.")

        return results[:max_items]

    async def _scrape_profile_ytdlp(self, url: str, output_dir: str, max_items: int) -> list:
        """Scrape profile videos with yt-dlp."""
        output_template = os.path.join(output_dir, '%(id)s.%(ext)s')

        cmd = [
            'yt-dlp',
            '--no-warnings',
            '-f', 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            '--merge-output-format', 'mp4',
            '-o', output_template,
            '--playlist-end', str(max_items),
            '--no-check-certificates',
            '--retries', '2',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            await asyncio.wait_for(process.communicate(), timeout=300)
        except asyncio.TimeoutError:
            process.kill()

        results = []
        for f in os.listdir(output_dir):
            path = os.path.join(output_dir, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                media_type = 'image'
            elif ext in ['.mp4', '.mkv', '.webm', '.mov']:
                media_type = 'video'
            else:
                continue
            results.append({'path': path, 'type': media_type})

        return results

    async def _scrape_profile_gallery_dl(self, url: str, output_dir: str, max_items: int) -> list:
        """Scrape profile images with gallery-dl."""
        cmd = [
            'gallery-dl',
            '--dest', output_dir,
            '--no-mtime',
            '--range', f'1-{max_items}',
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            await asyncio.wait_for(process.communicate(), timeout=300)
        except asyncio.TimeoutError:
            process.kill()

        results = []
        for root, _, files in os.walk(output_dir):
            for f in files:
                path = os.path.join(root, f)
                ext = os.path.splitext(f)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    results.append({'path': path, 'type': 'image'})
                elif ext in ['.mp4', '.mkv', '.webm', '.mov']:
                    results.append({'path': path, 'type': 'video'})

        return results

    def _find_downloaded_file(self, rand: str) -> dict:
        """Find the downloaded file after yt-dlp completes."""
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
