"""Metadata reset/freshening utilities."""

import asyncio
import random
import string
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _random_str(length: int = 12) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def reset_metadata(input_path: str, output_path: str) -> str:
    """Strip all metadata and write fresh metadata to avoid duplicate detection.

    This is critical for Instagram - reposted content gets flagged if metadata matches.
    """
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-map_metadata', '-1',
        '-metadata', f'creation_time={datetime.utcnow().isoformat()}Z',
        '-metadata', f'encoder=custom_{_random_str(12)}',
        '-metadata', f'comment={_random_str(16)}',
        '-metadata', f'title={_random_str(8)}',
        '-fflags', '+genpts',
        '-c', 'copy',
        output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"Metadata reset failed: {stderr.decode()}")
        raise Exception("Metadata reset failed")

    return output_path


async def get_metadata(input_path: str) -> dict:
    """Extract current metadata from a media file."""
    import json
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', input_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()

    try:
        data = json.loads(stdout.decode())
        return data.get('format', {}).get('tags', {})
    except (json.JSONDecodeError, ValueError):
        return {}
