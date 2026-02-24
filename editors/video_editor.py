"""Video editor - handles all video editing operations."""

import os
import re
import asyncio
import random
import string
import logging
from typing import Optional, Dict
from datetime import datetime

from core.detection import detect_text_overlay_region
from core.media_info import get_media_info

logger = logging.getLogger(__name__)


class VideoEditor:
    """Full-featured video editor with smart crop, watermark, text, dimensions, metadata."""

    def __init__(self, temp_dir: str, preset_manager=None):
        self.temp_dir = temp_dir
        self.preset_manager = preset_manager

    @staticmethod
    def _random_str(length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _build_filter_eq(self, filters: Dict) -> Optional[str]:
        """Build FFmpeg eq/colorbalance filter string from preset filters."""
        parts = []
        sat = filters.get('saturation', 1.0)
        con = filters.get('contrast', 1.0)
        bri = filters.get('brightness', 1.0)
        if sat != 1.0 or con != 1.0 or bri != 1.0:
            parts.append(f"eq=contrast={con}:brightness={bri - 1.0}:saturation={sat}")
        temp = filters.get('temperature', 0)
        if temp != 0:
            if temp > 0:
                parts.append(f"colorbalance=rs={temp / 100}:gs={temp / 200}:bs=-{temp / 100}")
            else:
                t = abs(temp)
                parts.append(f"colorbalance=rs=-{t / 100}:gs=-{t / 200}:bs={t / 100}")
        bp = filters.get('black_point', 0)
        if bp > 0:
            parts.append(f"curves=m='0/{bp / 255:.3f} 1/1'")
        return ','.join(parts) if parts else None

    async def process(
        self,
        input_path: str,
        output_path: str,
        crop_mode: str = 'smart',
        top_text: Optional[str] = None,
        watermark_text: Optional[str] = None,
        watermark_image: Optional[str] = None,
        dark_mode: bool = True,
        filter_preset: Optional[str] = None,
        target_width: int = 1080,
        target_height: int = 1920,
    ) -> str:
        """Process a video with all editing options.

        Args:
            input_path: Source video file
            output_path: Destination file
            crop_mode: smart, center, top, bottom, fit
            top_text: Text overlay above video
            watermark_text: Text watermark
            watermark_image: Path to watermark image
            dark_mode: True for black bg, False for white
            filter_preset: Name of color filter preset
            target_width: Output width in pixels
            target_height: Output height in pixels
        """
        info = get_media_info(input_path)
        src_w, src_h = info['width'], info['height']
        if src_w == 0 or src_h == 0:
            raise Exception("Could not read video dimensions")

        # Smart crop: detect existing text overlays
        text_region = None
        if crop_mode == 'smart':
            text_region = detect_text_overlay_region(input_path)
            if text_region:
                logger.info(
                    f"Detected text overlay: top={text_region.get('top_crop', 0)}px, "
                    f"bottom={text_region.get('bottom_crop', 0)}px"
                )
                src_w = text_region['w']
                src_h = text_region['h']

        bg_color = "black" if dark_mode else "white"
        text_color = "white" if dark_mode else "black"

        filter_parts = []

        # Pre-crop to remove text overlays
        if text_region:
            precrop = f"crop={text_region['w']}:{text_region['h']}:{text_region['x']}:{text_region['y']}"
            filter_parts.append(f"[0:v]{precrop}[precropped]")
            video_input = "[precropped]"
        else:
            video_input = "[0:v]"

        # Color filter
        filter_eq = None
        if filter_preset and filter_preset != 'none' and self.preset_manager:
            preset = self.preset_manager.get_preset(filter_preset)
            if preset:
                filter_eq = self._build_filter_eq(preset.get('filters', {}))

        # Dynamic text layout
        text_area_height = 0
        text_lines = []
        text_font_size = 58
        line_height = 78

        if top_text:
            clean_text = ''.join(c if (32 <= ord(c) <= 126) else ' ' for c in top_text)
            clean_text = re.sub(r' {2,}', ' ', clean_text).strip()

            total_chars = len(clean_text)
            if total_chars <= 40:
                text_font_size = 58
                max_chars_per_line = 22
            elif total_chars <= 80:
                text_font_size = 50
                max_chars_per_line = 26
            elif total_chars <= 120:
                text_font_size = 44
                max_chars_per_line = 30
            else:
                text_font_size = 38
                max_chars_per_line = 34

            # Scale font based on target dimensions relative to 1080 width
            scale_factor = target_width / 1080
            text_font_size = int(text_font_size * scale_factor)
            line_height = int(text_font_size * 1.4)

            words = clean_text.split()
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= max_chars_per_line:
                    current_line = (current_line + " " + word).strip()
                else:
                    if current_line:
                        text_lines.append(current_line)
                    current_line = word
            if current_line:
                text_lines.append(current_line)

            text_area_height = len(text_lines) * line_height + 80

        # Layout
        video_top_margin = text_area_height + 30 if top_text else 80
        video_bottom_margin = 80
        content_height = target_height - video_top_margin - video_bottom_margin
        content_width = target_width - 40

        src_aspect = src_w / src_h
        target_aspect = content_width / content_height

        use_fit_mode = (crop_mode == 'fit') or (text_region is not None)

        if use_fit_mode:
            if src_aspect > target_aspect:
                scaled_w = content_width
                scaled_h = int(content_width / src_aspect)
            else:
                scaled_h = content_height
                scaled_w = int(content_height * src_aspect)
            scaled_w = scaled_w if scaled_w % 2 == 0 else scaled_w - 1
            scaled_h = scaled_h if scaled_h % 2 == 0 else scaled_h - 1
            scale_filter = f"scale={scaled_w}:{scaled_h}"
        else:
            if src_aspect > target_aspect:
                scale_h = content_height
                scale_w = int(src_w * (content_height / src_h))
            else:
                scale_w = content_width
                scale_h = int(src_h * (content_width / src_w))
            scale_w = scale_w if scale_w % 2 == 0 else scale_w - 1
            scale_h = scale_h if scale_h % 2 == 0 else scale_h - 1
            crop_x = (scale_w - content_width) // 2
            if crop_mode == 'top':
                crop_y = 0
            elif crop_mode == 'bottom':
                crop_y = scale_h - content_height
            else:
                crop_y = (scale_h - content_height) // 2
            scale_filter = f"scale={scale_w}:{scale_h},crop={content_width}:{content_height}:{crop_x}:{crop_y}"
            scaled_w = content_width
            scaled_h = content_height

        video_filters = scale_filter
        if filter_eq:
            video_filters = f"{filter_eq},{video_filters}"
        filter_parts.append(f"{video_input}{video_filters},setsar=1[scaled]")

        # Background
        filter_parts.append(f"color={bg_color}:{target_width}x{target_height}:d=1,format=yuv420p[bg]")

        overlay_x = (target_width - scaled_w) // 2
        overlay_y = video_top_margin + (content_height - scaled_h) // 2
        filter_parts.append(f"[bg][scaled]overlay={overlay_x}:{overlay_y}:shortest=0[canvas]")

        current = "[canvas]"

        # Text overlays
        if top_text and text_lines:
            start_y = 40
            for i, line in enumerate(text_lines):
                escaped_line = line.replace("'", "'\\''").replace(":", "\\:").replace("\\", "\\\\")
                line_y = start_y + (i * line_height)
                out_label = f"[txt{i}]"
                filter_parts.append(
                    f"{current}drawtext="
                    f"text='{escaped_line}':"
                    f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"fontsize={text_font_size}:"
                    f"fontcolor={text_color}:"
                    f"x=(w-text_w)/2:"
                    f"y={line_y}"
                    f"{out_label}"
                )
                current = out_label
            filter_parts.append(f"{current}null[texted]")
            current = "[texted]"

        # Watermark
        wm_font_size = int(32 * (target_width / 1080))
        wm_margin = 20
        wm_opacity = 0.85

        if watermark_text:
            escaped_wm = watermark_text.replace("'", "'\\''").replace(":", "\\:")
            wm_y = overlay_y + 15
            filter_parts.append(
                f"{current}drawtext="
                f"text='{escaped_wm}':"
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"fontsize={wm_font_size}:"
                f"fontcolor=white@{wm_opacity}:"
                f"x=w-tw-{wm_margin}:"
                f"y={wm_y}:"
                f"shadowcolor=black@0.5:"
                f"shadowx=1:shadowy=1"
                f"[final]"
            )
        elif watermark_image and os.path.exists(watermark_image):
            filter_parts.append(
                f"[1:v]scale=100:-1,format=yuva420p,colorchannelmixer=aa={wm_opacity}[wm]"
            )
            wm_y = overlay_y + 15
            filter_parts.append(f"{current}[wm]overlay=W-w-{wm_margin}:{wm_y}[final]")
        else:
            filter_parts.append(f"{current}null[final]")

        filter_complex = ';'.join(filter_parts)

        wm_input = []
        if watermark_image and os.path.exists(watermark_image) and not watermark_text:
            wm_input = ['-i', watermark_image]

        # Calculate aspect ratio string
        if target_width == 1080 and target_height == 1920:
            aspect = '9:16'
        elif target_width == target_height:
            aspect = '1:1'
        else:
            aspect = f'{target_width}:{target_height}'

        cmd = [
            'ffmpeg', '-y', '-i', input_path, *wm_input,
            '-filter_complex', filter_complex,
            '-map', '[final]',
        ]
        if info.get('has_audio'):
            cmd.extend(['-map', '0:a?', '-c:a', 'aac', '-b:a', '192k'])
        cmd.extend([
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-pix_fmt', 'yuv420p', '-aspect', aspect,
            '-movflags', '+faststart',
            '-map_metadata', '-1',
            '-metadata', f'creation_time={datetime.utcnow().isoformat()}Z',
            '-metadata', f'encoder=custom_{self._random_str(12)}',
            '-metadata', f'comment={self._random_str(16)}',
            '-fflags', '+genpts',
            output_path
        ])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception("Video processing failed")
        return output_path
