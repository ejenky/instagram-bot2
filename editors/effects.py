"""Effects editor - border, retention filter, speed, voice effects, captions, etc."""

import os
import asyncio
import random
import logging
import glob as globlib
from typing import Optional

from core.config import (
    SLUDGE_CLIPS_DIR, MUSIC_DIR, FONTS_DIR,
    CAPTION_STYLES, VOICE_EFFECTS, TEXT_STYLES,
)

logger = logging.getLogger(__name__)


async def add_border(input_path: str, output_path: str, color: str = '#000000',
                     width: int = 40) -> str:
    """Add a colored border/frame around the video."""
    pad = width * 2
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f'pad=iw+{pad}:ih+{pad}:{width}:{width}:color={color}',
        '-c:a', 'copy',
        output_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Border failed: {stderr.decode()}")
        raise Exception("Failed to add border")
    return output_path


async def add_text_overlay(input_path: str, output_path: str, text: str,
                           position: str = 'bottom', style: str = 'bold_white',
                           fontsize: int = 48) -> str:
    """Burn text onto video at specified position with specified style."""
    style_cfg = TEXT_STYLES.get(style, TEXT_STYLES['bold_white'])

    # Escape text for ffmpeg
    escaped = text.replace("'", "'\\''").replace(":", "\\:").replace("\\", "\\\\")

    fontfile = f"{FONTS_DIR}/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(fontfile):
        fontfile = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    actual_size = int(fontsize * style_cfg.get('fontsize_multiplier', 1.0))

    # Position calculations
    if position == 'top':
        y_expr = '50'
    elif position == 'center':
        y_expr = '(h-text_h)/2'
    else:  # bottom
        y_expr = 'h-text_h-50'

    # Build drawtext filter
    dt = (
        f"drawtext=text='{escaped}':"
        f"fontfile={fontfile}:"
        f"fontsize={actual_size}:"
        f"fontcolor={style_cfg.get('fontcolor', 'white')}:"
        f"x=(w-text_w)/2:y={y_expr}"
    )

    # Add style-specific options
    if style_cfg.get('borderw', 0) > 0:
        dt += f":borderw={style_cfg['borderw']}:bordercolor={style_cfg.get('bordercolor', 'black')}"
    if style_cfg.get('box'):
        dt += f":box=1:boxcolor={style_cfg['boxcolor']}:boxborderw={style_cfg.get('boxborderw', 5)}"
    if style_cfg.get('shadowcolor'):
        dt += f":shadowcolor={style_cfg['shadowcolor']}:shadowx={style_cfg.get('shadowx', 2)}:shadowy={style_cfg.get('shadowy', 2)}"

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', dt,
        '-c:a', 'copy',
        output_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Text overlay failed: {stderr.decode()}")
        raise Exception("Failed to add text overlay")
    return output_path


def _find_sludge_clip(category: str) -> Optional[str]:
    """Find a random sludge clip from the specified category."""
    from core.config import SLUDGE_CATEGORIES
    cat = SLUDGE_CATEGORIES.get(category)
    if not cat:
        return None

    prefix = cat['prefix']
    pattern = os.path.join(SLUDGE_CLIPS_DIR, f'{prefix}_*.mp4')
    clips = globlib.glob(pattern)
    if not clips:
        # Try without underscore numbering
        pattern = os.path.join(SLUDGE_CLIPS_DIR, f'{prefix}*.mp4')
        clips = globlib.glob(pattern)
    return random.choice(clips) if clips else None


async def add_retention_filter(input_path: str, output_path: str,
                               category: str = 'subway_surfers',
                               layout: str = 'top_bottom') -> str:
    """Add a retention/sludge clip alongside the main video.

    Layouts:
    - top_bottom: Main on top, sludge on bottom (default for Reels/Shorts)
    - left_right: Side by side (for landscape)
    - pip: Small sludge clip in corner
    """
    sludge_path = _find_sludge_clip(category)
    if not sludge_path:
        logger.warning(f"No sludge clips found for category: {category}")
        raise Exception(f"No sludge clips available for '{category}'. Add clips to {SLUDGE_CLIPS_DIR}")

    if layout == 'top_bottom':
        filter_complex = (
            "[0:v]scale=1080:960,setsar=1[top];"
            "[1:v]scale=1080:960,setsar=1,loop=-1:size=32767[bottom];"
            "[top][bottom]vstack=inputs=2[v]"
        )
    elif layout == 'left_right':
        filter_complex = (
            "[0:v]scale=540:960,setsar=1[left];"
            "[1:v]scale=540:960,setsar=1,loop=-1:size=32767[right];"
            "[left][right]hstack=inputs=2[v]"
        )
    else:  # pip
        filter_complex = (
            "[1:v]scale=270:480,setsar=1,loop=-1:size=32767[pip];"
            "[0:v]scale=1080:1920,setsar=1[main];"
            "[main][pip]overlay=W-w-20:H-h-20[v]"
        )

    cmd = [
        'ffmpeg', '-y', '-i', input_path, '-i', sludge_path,
        '-filter_complex', filter_complex,
        '-map', '[v]', '-map', '0:a?',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-c:a', 'aac',
        '-shortest',
        output_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Retention filter failed: {stderr.decode()}")
        raise Exception("Failed to add retention filter")
    return output_path


async def change_speed(input_path: str, output_path: str, speed: float = 1.0) -> str:
    """Change video playback speed."""
    if speed == 1.0:
        return input_path

    video_pts = 1.0 / speed

    # atempo must be between 0.5 and 100, chain for extreme values
    audio_filters = []
    remaining = speed
    while remaining > 2.0:
        audio_filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        audio_filters.append("atempo=0.5")
        remaining /= 0.5
    audio_filters.append(f"atempo={remaining:.4f}")

    af = ','.join(audio_filters)

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f'setpts={video_pts:.4f}*PTS',
        '-af', af,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-c:a', 'aac',
        output_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Speed change failed: {stderr.decode()}")
        raise Exception("Failed to change speed")
    return output_path


async def apply_voice_effect(input_path: str, output_path: str,
                             effect: str = 'deep') -> str:
    """Apply voice/audio effect to video."""
    effect_cfg = VOICE_EFFECTS.get(effect)
    if not effect_cfg:
        raise Exception(f"Unknown voice effect: {effect}")

    if 'filter' in effect_cfg:
        af = effect_cfg['filter']
    else:
        rate = effect_cfg.get('rate', 1.0)
        tempo = effect_cfg.get('tempo', 1.0)
        af = f"asetrate=44100*{rate},aresample=44100,atempo={tempo}"

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-af', af,
        '-c:v', 'copy',
        output_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Voice effect failed: {stderr.decode()}")
        raise Exception("Failed to apply voice effect")
    return output_path


async def burn_subtitles(input_path: str, output_path: str,
                         srt_path: str, style: str = 'standard') -> str:
    """Burn SRT subtitles onto video with specified style."""
    style_cfg = CAPTION_STYLES.get(style, CAPTION_STYLES['standard'])

    force_style = (
        f"FontName={style_cfg.get('font', 'DejaVuSans-Bold.ttf')},"
        f"FontSize={style_cfg.get('fontsize', 24)},"
        f"PrimaryColour={style_cfg.get('color', '&H00FFFFFF')},"
        f"OutlineColour={style_cfg.get('outline_color', '&H00000000')},"
        f"Outline={style_cfg.get('outline', 2)},"
        f"Shadow={style_cfg.get('shadow', 1)},"
        f"MarginV={style_cfg.get('margin_v', 60)}"
    )

    # Escape path for ffmpeg subtitles filter
    escaped_srt = srt_path.replace("'", "'\\''").replace(":", "\\:")

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f"subtitles='{escaped_srt}':force_style='{force_style}'",
        '-c:a', 'copy',
        output_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Subtitle burn failed: {stderr.decode()}")
        raise Exception("Failed to burn subtitles")
    return output_path


async def overlay_voiceover(input_path: str, voiceover_path: str,
                            output_path: str, mode: str = 'replace') -> str:
    """Add voiceover to video.

    Modes:
    - replace: Replace original audio entirely
    - mix: Mix voiceover with original audio (original at 30% volume)
    """
    if mode == 'mix':
        cmd = [
            'ffmpeg', '-y', '-i', input_path, '-i', voiceover_path,
            '-filter_complex',
            "[0:a]volume=0.3[bg];[1:a]volume=1.0[vo];[bg][vo]amix=inputs=2:duration=shortest",
            '-map', '0:v', '-c:v', 'copy',
            output_path
        ]
    else:  # replace
        cmd = [
            'ffmpeg', '-y', '-i', input_path, '-i', voiceover_path,
            '-map', '0:v', '-map', '1:a',
            '-c:v', 'copy', '-c:a', 'aac',
            '-shortest',
            output_path
        ]

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Voiceover overlay failed: {stderr.decode()}")
        raise Exception("Failed to overlay voiceover")
    return output_path


async def add_background_music(input_path: str, music_path: str,
                               output_path: str, music_volume: float = 0.15) -> str:
    """Add background music to video, mixed with original audio."""
    cmd = [
        'ffmpeg', '-y', '-i', input_path, '-i', music_path,
        '-filter_complex',
        f"[1:a]volume={music_volume}[music];[0:a][music]amix=inputs=2:duration=shortest[a]",
        '-map', '0:v', '-map', '[a]',
        '-c:v', 'copy', '-c:a', 'aac',
        output_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Background music failed: {stderr.decode()}")
        raise Exception("Failed to add background music")
    return output_path


async def convert_aspect_ratio(input_path: str, output_path: str,
                               target_w: int = 1080, target_h: int = 1920,
                               method: str = 'blur') -> str:
    """Convert video to target aspect ratio.

    Methods:
    - crop: Center crop to fit
    - pad: Add black bars
    - blur: Pad with blurred background (best for Reels)
    """
    if method == 'crop':
        vf = f"crop=ih*{target_w}/{target_h}:ih,scale={target_w}:{target_h}"
    elif method == 'pad':
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
        )
    else:  # blur
        vf = (
            f"split[original][bg];"
            f"[bg]scale={target_w}:{target_h},boxblur=20:20[blurred];"
            f"[original]scale=-1:{target_h}[scaled];"
            f"[blurred][scaled]overlay=(W-w)/2:(H-h)/2"
        )

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', vf,
        '-c:a', 'copy',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        output_path
    ]

    # For blur method, use filter_complex instead of -vf
    if method == 'blur':
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-filter_complex', vf,
            '-c:a', 'copy',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            output_path
        ]

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Aspect ratio conversion failed: {stderr.decode()}")
        raise Exception("Failed to convert aspect ratio")
    return output_path


async def create_slideshow(image_paths: list, output_path: str,
                           duration_per_slide: float = 3.0,
                           target_w: int = 1080, target_h: int = 1920,
                           transition: str = 'fade') -> str:
    """Create a video slideshow from images with Ken Burns effect and transitions."""
    if not image_paths:
        raise Exception("No images provided for slideshow")

    # Build complex filter for Ken Burns zoom + transitions
    inputs = []
    filter_parts = []
    d = int(duration_per_slide * 30)  # frames at 30fps

    for i, img_path in enumerate(image_paths):
        inputs.extend(['-loop', '1', '-t', str(duration_per_slide), '-i', img_path])
        filter_parts.append(
            f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"zoompan=z='min(zoom+0.001,1.3)':d={d}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={target_w}x{target_h}[v{i}]"
        )

    # Chain xfade transitions
    if len(image_paths) == 1:
        filter_complex = ';'.join(filter_parts)
        final_label = f'[v0]'
    else:
        xfade_parts = list(filter_parts)
        prev = '[v0]'
        for i in range(1, len(image_paths)):
            offset = duration_per_slide * i - 0.5 * i
            out = f'[t{i}]' if i < len(image_paths) - 1 else '[out]'
            xfade_parts.append(
                f"{prev}[v{i}]xfade=transition={transition}:"
                f"duration=0.5:offset={offset:.1f}{out}"
            )
            prev = out
        filter_complex = ';'.join(xfade_parts)
        final_label = '[out]'

    cmd = [
        'ffmpeg', '-y', *inputs,
        '-filter_complex', filter_complex,
        '-map', final_label,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Slideshow creation failed: {stderr.decode()}")
        raise Exception("Failed to create slideshow")
    return output_path


async def apply_template_format(input_path: str, output_path: str,
                                template: str = 'reel') -> str:
    """Apply a video format template.

    Templates:
    - reel: 9:16 (1080x1920)
    - story: 9:16 max 15 seconds
    - square: 1:1 (1080x1080)
    - landscape: 16:9 (1920x1080)
    """
    if template == 'reel':
        return await convert_aspect_ratio(input_path, output_path, 1080, 1920, 'blur')
    elif template == 'story':
        # 9:16 with 15s max
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-t', '15',
            '-filter_complex',
            "split[original][bg];"
            "[bg]scale=1080:1920,boxblur=20:20[blurred];"
            "[original]scale=-1:1920[scaled];"
            "[blurred][scaled]overlay=(W-w)/2:(H-h)/2",
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac',
            output_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise Exception("Failed to apply story template")
        return output_path
    elif template == 'square':
        return await convert_aspect_ratio(input_path, output_path, 1080, 1080, 'crop')
    elif template == 'landscape':
        return await convert_aspect_ratio(input_path, output_path, 1920, 1080, 'pad')
    else:
        raise Exception(f"Unknown template: {template}")


def list_music_files(category: Optional[str] = None) -> list:
    """List available background music files."""
    if not os.path.exists(MUSIC_DIR):
        return []

    files = []
    for f in os.listdir(MUSIC_DIR):
        if f.endswith(('.mp3', '.wav', '.m4a', '.ogg')):
            if category is None or f.startswith(category):
                files.append({
                    'path': os.path.join(MUSIC_DIR, f),
                    'name': os.path.splitext(f)[0],
                })
    return sorted(files, key=lambda x: x['name'])


def list_sludge_clips() -> dict:
    """List available sludge clips by category."""
    from core.config import SLUDGE_CATEGORIES
    result = {}
    for key, cat in SLUDGE_CATEGORIES.items():
        prefix = cat['prefix']
        pattern = os.path.join(SLUDGE_CLIPS_DIR, f'{prefix}*.mp4')
        clips = globlib.glob(pattern)
        result[key] = {'name': cat['name'], 'count': len(clips)}
    return result
