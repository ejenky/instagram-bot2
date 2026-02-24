"""Content detection utilities - text overlay detection, crop detection."""

import re
import os
import json
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)


def detect_content_region(video_path):
    """Detect actual video content area, excluding text bars and overlays."""
    probe = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', video_path
    ], capture_output=True, text=True)

    try:
        data = json.loads(probe.stdout)
        width = height = 0
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = stream.get('width', 0)
                height = stream.get('height', 0)
                break
        else:
            return None
    except (json.JSONDecodeError, ValueError):
        return None

    if width == 0 or height == 0:
        return None

    result = subprocess.run([
        'ffmpeg', '-i', video_path, '-vframes', '30', '-vf',
        'cropdetect=24:16:0', '-f', 'null', '-'
    ], capture_output=True, text=True, timeout=30)

    crop_lines = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', result.stderr)
    if crop_lines:
        w, h, x, y = map(int, crop_lines[-1])
        if h < height * 0.95 or w < width * 0.95:
            return {'w': w, 'h': h, 'x': x, 'y': y, 'orig_w': width, 'orig_h': height}

    return None


def detect_text_overlay_region(video_path):
    """Smart detection of text overlay regions by comparing edge colors."""
    probe = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', video_path
    ], capture_output=True, text=True)

    try:
        data = json.loads(probe.stdout)
        width = height = 0
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = stream.get('width', 0)
                height = stream.get('height', 0)
                break
        else:
            return None
    except (json.JSONDecodeError, ValueError):
        return None

    if width == 0 or height == 0:
        return None

    with tempfile.NamedTemporaryFile(suffix='.ppm', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        subprocess.run([
            'ffmpeg', '-y', '-ss', '0.5', '-i', video_path, '-vframes', '1',
            '-f', 'image2', tmp_path
        ], capture_output=True, timeout=30)

        if not os.path.exists(tmp_path):
            return None

        with open(tmp_path, 'rb') as f:
            header = f.readline()
            line = f.readline()
            while line.startswith(b'#'):
                line = f.readline()
            dims = line.decode().strip().split()
            if len(dims) < 2:
                return None
            img_w, img_h = int(dims[0]), int(dims[1])
            f.readline()
            pixels = f.read()

        if len(pixels) < img_w * img_h * 3:
            return None

        def get_edge_avg_color(y_pos):
            start = y_pos * img_w * 3
            row = pixels[start:start + img_w * 3]
            if len(row) < img_w * 3:
                return None
            colors = []
            for i in range(30):
                idx = i * 3
                if idx + 2 < len(row):
                    colors.append((row[idx], row[idx + 1], row[idx + 2]))
                idx = (img_w - 1 - i) * 3
                if idx + 2 < len(row):
                    colors.append((row[idx], row[idx + 1], row[idx + 2]))
            if not colors:
                return None
            return (
                sum(c[0] for c in colors) / len(colors),
                sum(c[1] for c in colors) / len(colors),
                sum(c[2] for c in colors) / len(colors)
            )

        def colors_similar(c1, c2, threshold=45):
            if not c1 or not c2:
                return False
            return all(abs(c1[i] - c2[i]) < threshold for i in range(3))

        ref_top_color = get_edge_avg_color(5)
        top_crop = 0
        if ref_top_color:
            for y in range(10, min(img_h // 2, 800)):
                curr_color = get_edge_avg_color(y)
                if not colors_similar(ref_top_color, curr_color):
                    top_crop = y
                    break

        ref_bottom_color = get_edge_avg_color(img_h - 5)
        bottom_crop = img_h
        if ref_bottom_color:
            for y in range(img_h - 10, max(img_h // 2, 200), -1):
                curr_color = get_edge_avg_color(y)
                if not colors_similar(ref_bottom_color, curr_color):
                    bottom_crop = y
                    break

        content_height = bottom_crop - top_crop
        top_percent = top_crop / img_h
        bottom_percent = (img_h - bottom_crop) / img_h

        if (top_percent > 0.02 or bottom_percent > 0.02) and content_height > img_h * 0.3:
            scale_y = height / img_h
            logger.info(
                f"Smart crop: top={top_crop}px ({top_percent * 100:.1f}%), "
                f"bottom={img_h - bottom_crop}px ({bottom_percent * 100:.1f}%)"
            )
            return {
                'w': width,
                'h': int(content_height * scale_y),
                'x': 0,
                'y': int(top_crop * scale_y),
                'orig_w': width,
                'orig_h': height,
                'top_crop': int(top_crop * scale_y),
                'bottom_crop': int((img_h - bottom_crop) * scale_y)
            }

        return None

    except Exception as e:
        logger.warning(f"Text overlay detection failed: {e}")
        return None
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
