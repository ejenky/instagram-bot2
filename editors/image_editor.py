"""Image editor - handles all image editing operations."""

import os
import re
import asyncio
import random
import string
import logging
from typing import Optional, Dict
from datetime import datetime

from core.media_info import get_media_info

logger = logging.getLogger(__name__)


class ImageEditor:
    """Image editor with crop, watermark, text, dimensions, filters."""

    def __init__(self, temp_dir: str, preset_manager=None):
        self.temp_dir = temp_dir
        self.preset_manager = preset_manager

    @staticmethod
    def _random_str(length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _build_filter_eq(self, filters: Dict) -> Optional[str]:
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
        filter_preset: Optional[str] = None,
        dark_mode: bool = True,
        target_width: int = 1080,
        target_height: int = 1920,
    ) -> str:
        """Process an image with all editing options."""
        info = get_media_info(input_path)
        src_w, src_h = info['width'], info['height']
        if src_w == 0 or src_h == 0:
            raise Exception("Could not read image dimensions")

        bg_color = "black" if dark_mode else "white"
        text_color = "white" if dark_mode else "black"

        filter_parts = []

        # Color filter
        filter_eq = None
        if filter_preset and filter_preset != 'none' and self.preset_manager:
            preset = self.preset_manager.get_preset(filter_preset)
            if preset:
                filter_eq = self._build_filter_eq(preset.get('filters', {}))

        # Text layout
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

        image_top_margin = text_area_height + 30 if top_text else 80
        image_bottom_margin = 80
        content_height = target_height - image_top_margin - image_bottom_margin
        content_width = target_width - 40

        src_aspect = src_w / src_h
        target_aspect = content_width / content_height

        if src_aspect > target_aspect:
            scaled_w = content_width
            scaled_h = int(content_width / src_aspect)
        else:
            scaled_h = content_height
            scaled_w = int(content_height * src_aspect)
        scaled_w = scaled_w if scaled_w % 2 == 0 else scaled_w - 1
        scaled_h = scaled_h if scaled_h % 2 == 0 else scaled_h - 1

        scale_filter = f"scale={scaled_w}:{scaled_h}"
        if filter_eq:
            scale_filter = f"{filter_eq},{scale_filter}"
        filter_parts.append(f"[0:v]{scale_filter},setsar=1[scaled]")

        filter_parts.append(f"color={bg_color}:{target_width}x{target_height}[bg]")

        overlay_x = (target_width - scaled_w) // 2
        overlay_y = image_top_margin + (content_height - scaled_h) // 2
        filter_parts.append(f"[bg][scaled]overlay={overlay_x}:{overlay_y}[canvas]")

        current = "[canvas]"

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

        cmd = [
            'ffmpeg', '-y', '-i', input_path, *wm_input,
            '-filter_complex', filter_complex,
            '-map', '[final]', '-q:v', '2',
            '-map_metadata', '-1',
            '-metadata', f'comment={self._random_str(16)}',
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception("Image processing failed")
        return output_path
