"""Media randomization for anti-detection on social platforms.

Applies subtle visual/audio changes so content registers as unique,
preventing Instagram/TikTok from detecting reposts.
"""

import os
import asyncio
import random
import string
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _random_str(length: int = 12) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def randomize_video(input_path: str, output_path: str) -> str:
    """Apply full anti-detection randomization to a video.

    Applies:
    - Random brightness shift (0.01-0.03)
    - Random saturation shift (1.01-1.05)
    - Random crop (2-8 pixels from edges)
    - Random audio pitch shift (imperceptible, 1.01-1.03)
    - Complete metadata strip + re-encode
    """
    brightness = random.uniform(0.01, 0.03)
    saturation = random.uniform(1.01, 1.05)
    crop_x = random.randint(2, 8)
    crop_y = random.randint(2, 8)
    audio_rate = random.uniform(1.01, 1.03)

    vf = (
        f"eq=brightness={brightness:.4f}:saturation={saturation:.4f},"
        f"crop=iw-{crop_x}:ih-{crop_y},"
        f"scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos"
    )
    af = f"asetrate=44100*{audio_rate:.4f},aresample=44100"

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', vf,
        '-af', af,
        '-map_metadata', '-1',
        '-metadata', f'creation_time={datetime.utcnow().isoformat()}Z',
        '-metadata', f'encoder=custom_{_random_str(12)}',
        '-metadata', f'comment={_random_str(16)}',
        '-metadata', f'title={_random_str(8)}',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        '-fflags', '+genpts',
        output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"Video randomization failed: {stderr.decode()}")
        raise Exception("Video randomization failed")

    return output_path


async def randomize_image(input_path: str, output_path: str) -> str:
    """Apply anti-detection randomization to an image.

    Applies:
    - Strip ALL EXIF data
    - Re-encode as JPEG with random quality (92-97%)
    - Random brightness adjustment (±1-2%)
    - Changes file hash completely
    """
    quality = random.randint(92, 97)
    brightness = random.uniform(-0.02, 0.02)

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f'eq=brightness={brightness:.4f}',
        '-map_metadata', '-1',
        '-q:v', str(int((100 - quality) / 3) + 1),  # ffmpeg quality scale
        output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"Image randomization failed: {stderr.decode()}")
        raise Exception("Image randomization failed")

    return output_path


async def quick_randomize(input_path: str, output_path: str, is_video: bool = True) -> str:
    """Quick randomization - metadata strip + subtle re-encode only."""
    if is_video:
        return await randomize_video(input_path, output_path)
    else:
        return await randomize_image(input_path, output_path)
