"""Media info extraction using ffprobe."""

import json
import subprocess
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def get_media_info(path: str) -> Dict:
    """Extract media information using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        info = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return {
            'width': 0, 'height': 0, 'duration': 0,
            'is_video': False, 'has_audio': False
        }

    video_stream = next(
        (s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None
    )
    audio_stream = next(
        (s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), None
    )

    if video_stream:
        rotation = int(video_stream.get('tags', {}).get('rotate', 0))
        w = int(video_stream.get('width', 0))
        h = int(video_stream.get('height', 0))
        if rotation in [90, 270]:
            w, h = h, w
        duration = float(info.get('format', {}).get('duration', 0))
        codec = video_stream.get('codec_name', '')
        fps_str = video_stream.get('r_frame_rate', '30/1')
        try:
            num, den = fps_str.split('/')
            fps = round(int(num) / int(den), 2)
        except (ValueError, ZeroDivisionError):
            fps = 30.0
        bitrate = int(info.get('format', {}).get('bit_rate', 0))

        return {
            'width': w,
            'height': h,
            'duration': duration,
            'is_video': audio_stream is not None or duration > 0,
            'has_audio': audio_stream is not None,
            'codec': codec,
            'fps': fps,
            'bitrate': bitrate,
        }

    return {
        'width': 0, 'height': 0, 'duration': 0,
        'is_video': False, 'has_audio': False
    }
