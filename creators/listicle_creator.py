"""Listicle/Ranking video creator - automated CapCut-style 'Top N' video layout.

Creates a 9:16 (1080x1920) MP4 with:
- Black background frame
- Persistent title bar at top with multi-colored text
- Numbered list on left side with highlight for current clip
- Labels that reveal progressively as each clip plays
- Clips stitched together sequentially
- Optional background music (original clip audio muted)
"""

import os
import asyncio
import random
import string
import shutil
import logging
from typing import List, Tuple, Optional, Dict
from datetime import datetime

from core.media_info import get_media_info

logger = logging.getLogger(__name__)


class ListicleCreator:
    """Creates a ranking/listicle style video with title bar, numbered list, and clips."""

    # Frame dimensions
    FRAME_WIDTH = 1080
    FRAME_HEIGHT = 1920

    # Title bar layout
    TITLE_BAR_HEIGHT = 140
    TITLE_FONT_SIZE = 44
    TITLE_LINE_HEIGHT = 54
    TITLE_TOP_PADDING = 25

    # Numbered list layout
    LIST_LEFT_MARGIN = 50
    NUMBER_FONT_SIZE = 72
    NUMBER_BG_SIZE = 80
    LABEL_FONT_SIZE = 34
    LABEL_LEFT_OFFSET = 95

    # Content area (where video clips appear, below title bar)
    CONTENT_TOP = 150
    CONTENT_BOTTOM_MARGIN = 40

    # Colors
    ACTIVE_NUMBER_COLOR = '#FF0000'
    DIM_NUMBER_COLOR = '#555555'
    SHOWN_NUMBER_COLOR = '#AAAAAA'
    LABEL_COLOR = 'white'
    LABEL_DIM_COLOR = '#CCCCCC'

    # Fonts
    FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

    COLOR_MAP = {
        'red': '#FF0000',
        'white': 'white',
        'blue': '#0088FF',
        'yellow': '#FFD700',
        'green': '#00FF00',
        'cyan': '#00FFFF',
        'pink': '#FF69B4',
        'orange': '#FF8C00',
        'purple': '#9B59B6',
        'gold': '#FFD700',
        'black': 'black',
    }

    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.title_segments: List[Tuple[str, str]] = []  # [(text, color), ...]
        self.clips: List[Dict] = []  # [{'path': str, 'start': float, 'end': float|None}]
        self.labels: List[str] = []
        self.number_colors: List[str] = []  # optional per-number custom colors
        self.background_music: Optional[str] = None
        self.bg_music_volume: float = 0.3

    @staticmethod
    def _random_str(length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Sanitize text for FFmpeg drawtext filter (ASCII-safe, escaped)."""
        clean = ''.join(c if (32 <= ord(c) <= 126) else '' for c in text)
        clean = clean.replace("'", "\u2019")  # replace quotes with unicode right quote
        clean = clean.replace(":", "\\:")
        clean = clean.replace("\\", "\\\\")
        clean = clean.replace("%", "%%%%")
        return clean.strip()

    @staticmethod
    def _estimate_text_width(text: str, fontsize: int) -> int:
        """Estimate text pixel width for DejaVu Sans Bold."""
        width = 0
        for char in text:
            if char == ' ':
                width += fontsize * 0.33
            elif char.isupper():
                width += fontsize * 0.72
            elif char in 'mwMW':
                width += fontsize * 0.85
            elif char in 'ijlIL!|':
                width += fontsize * 0.35
            else:
                width += fontsize * 0.58
        return int(width)

    @classmethod
    def _resolve_color(cls, color_name: str) -> str:
        """Resolve color name to FFmpeg-compatible color value."""
        return cls.COLOR_MAP.get(color_name.lower().strip(), color_name)

    def set_title(self, segments: List[Tuple[str, str]]):
        """Set title as a list of (text, color_name) segments."""
        self.title_segments = segments

    def add_clip(self, path: str, start: float = 0.0, end: Optional[float] = None):
        """Add a video clip to the timeline."""
        self.clips.append({'path': path, 'start': start, 'end': end})

    def set_labels(self, labels: List[str]):
        """Set labels for each numbered item."""
        self.labels = labels

    def set_number_colors(self, colors: List[str]):
        """Set custom colors for each number when highlighted."""
        self.number_colors = colors

    def set_background_music(self, path: str, volume: float = 0.3):
        """Set background music track."""
        self.background_music = path
        self.bg_music_volume = volume

    def clear(self):
        """Reset all settings."""
        self.title_segments.clear()
        self.clips.clear()
        self.labels.clear()
        self.number_colors.clear()
        self.background_music = None
        self.bg_music_volume = 0.3

    def _layout_title_lines(self) -> List[List[Tuple[str, str]]]:
        """Break title segments into lines that fit within the frame width."""
        max_width = self.FRAME_WIDTH - 80  # 40px margin each side
        lines: List[List[Tuple[str, str]]] = []
        current_line: List[Tuple[str, str]] = []
        current_width = 0

        for text, color in self.title_segments:
            seg_width = self._estimate_text_width(text, self.TITLE_FONT_SIZE)
            space_width = int(self.TITLE_FONT_SIZE * 0.33) if current_line else 0

            if current_width + space_width + seg_width > max_width and current_line:
                lines.append(current_line)
                current_line = [(text, color)]
                current_width = seg_width
            else:
                current_line.append((text, color))
                current_width += space_width + seg_width

        if current_line:
            lines.append(current_line)

        return lines if lines else [[("Listicle", "white")]]

    def _calculate_list_positions(self, num_items: int) -> List[int]:
        """Calculate y positions for each numbered item, evenly distributed."""
        available_height = self.FRAME_HEIGHT - self.CONTENT_TOP - 100
        # Distribute items evenly with margin from top and bottom
        top_start = self.CONTENT_TOP + 80
        if num_items <= 1:
            return [top_start]
        spacing = min(280, available_height // (num_items + 1))
        return [top_start + i * spacing for i in range(num_items)]

    async def _prepare_clip_with_overlays(self, clip_index: int) -> str:
        """Prepare a single clip with all graphical overlays baked in."""
        clip = self.clips[clip_index]
        output = os.path.join(
            self.temp_dir, f'listicle_clip_{clip_index}_{self._random_str()}.mp4'
        )

        # Trim arguments
        input_args = []
        if clip.get('start', 0) > 0:
            input_args.extend(['-ss', str(clip['start'])])
        if clip.get('end') is not None:
            input_args.extend(['-to', str(clip['end'])])

        num_items = len(self.clips)
        list_positions = self._calculate_list_positions(num_items)

        # Build filter_complex
        filters = []

        # Scale clip to fit content area within the 9:16 frame
        content_height = self.FRAME_HEIGHT - self.CONTENT_TOP - self.CONTENT_BOTTOM_MARGIN
        content_width = self.FRAME_WIDTH

        filters.append(
            f"[0:v]scale={content_width}:{content_height}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={content_width}:{content_height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1[scaled]"
        )

        # Black canvas at full frame size
        filters.append(
            f"color=black:{self.FRAME_WIDTH}x{self.FRAME_HEIGHT}:d=1,"
            f"format=yuv420p[bg]"
        )

        # Overlay scaled clip onto canvas
        filters.append(f"[bg][scaled]overlay=0:{self.CONTENT_TOP}:shortest=0[canvas]")

        current = "[canvas]"

        # --- Title bar ---
        # Dark semi-transparent bar
        filters.append(
            f"{current}drawbox="
            f"x=0:y=0:w={self.FRAME_WIDTH}:h={self.TITLE_BAR_HEIGHT}:"
            f"color=black@0.92:t=fill[titlebar]"
        )
        current = "[titlebar]"

        # Title text (multi-colored segments)
        if self.title_segments:
            title_lines = self._layout_title_lines()

            for line_idx, line_segments in enumerate(title_lines):
                # Total width for centering
                total_width = sum(
                    self._estimate_text_width(seg[0], self.TITLE_FONT_SIZE)
                    for seg in line_segments
                )
                total_width += (len(line_segments) - 1) * int(self.TITLE_FONT_SIZE * 0.33)

                start_x = max(10, (self.FRAME_WIDTH - total_width) // 2)
                current_x = start_x
                line_y = self.TITLE_TOP_PADDING + line_idx * self.TITLE_LINE_HEIGHT

                for seg_idx, (seg_text, seg_color) in enumerate(line_segments):
                    sanitized = self._sanitize_text(seg_text)
                    if not sanitized:
                        continue

                    color_val = self._resolve_color(seg_color)
                    out_label = f"[ttl_{line_idx}_{seg_idx}]"

                    filters.append(
                        f"{current}drawtext="
                        f"text='{sanitized}':"
                        f"fontfile={self.FONT_BOLD}:"
                        f"fontsize={self.TITLE_FONT_SIZE}:"
                        f"fontcolor={color_val}:"
                        f"x={current_x}:y={line_y}:"
                        f"shadowcolor=black@0.6:shadowx=2:shadowy=2"
                        f"{out_label}"
                    )
                    current = out_label
                    current_x += self._estimate_text_width(seg_text, self.TITLE_FONT_SIZE)
                    current_x += int(self.TITLE_FONT_SIZE * 0.33)

        # --- Numbered list ---
        for i in range(num_items):
            num_y = list_positions[i]
            number_text = str(i + 1)

            # Style based on relationship to current clip
            if i == clip_index:
                num_color = self.ACTIVE_NUMBER_COLOR
                num_fontsize = self.NUMBER_FONT_SIZE + 8
            elif i < clip_index:
                num_color = self.SHOWN_NUMBER_COLOR
                num_fontsize = self.NUMBER_FONT_SIZE
            else:
                num_color = self.DIM_NUMBER_COLOR
                num_fontsize = self.NUMBER_FONT_SIZE

            # Override with custom per-number color when active
            if i == clip_index and self.number_colors and i < len(self.number_colors):
                num_color = self._resolve_color(self.number_colors[i])

            # Number background box (semi-transparent)
            bg_x = self.LIST_LEFT_MARGIN - 10
            bg_y = num_y - 5
            out_label = f"[nbg_{i}]"
            filters.append(
                f"{current}drawbox="
                f"x={bg_x}:y={bg_y}:"
                f"w={self.NUMBER_BG_SIZE}:h={self.NUMBER_BG_SIZE}:"
                f"color=black@0.6:t=fill"
                f"{out_label}"
            )
            current = out_label

            # Number text
            num_x = self.LIST_LEFT_MARGIN + (
                self.NUMBER_BG_SIZE - self._estimate_text_width(number_text, num_fontsize)
            ) // 2
            out_label = f"[num_{i}]"
            filters.append(
                f"{current}drawtext="
                f"text='{number_text}':"
                f"fontfile={self.FONT_BOLD}:"
                f"fontsize={num_fontsize}:"
                f"fontcolor={num_color}:"
                f"x={num_x}:y={num_y}:"
                f"shadowcolor=black@0.8:shadowx=2:shadowy=2"
                f"{out_label}"
            )
            current = out_label

            # Label text (visible for current and past clips only)
            if i <= clip_index and self.labels and i < len(self.labels):
                label_text = self._sanitize_text(self.labels[i])
                if label_text:
                    label_x = self.LIST_LEFT_MARGIN + self.LABEL_LEFT_OFFSET
                    label_y = num_y + (self.NUMBER_FONT_SIZE - self.LABEL_FONT_SIZE) // 2

                    label_color = self.LABEL_COLOR if i == clip_index else self.LABEL_DIM_COLOR

                    # Label background for readability
                    lbl_bg_w = self._estimate_text_width(
                        self.labels[i], self.LABEL_FONT_SIZE
                    ) + 20
                    lbl_bg_h = self.LABEL_FONT_SIZE + 14
                    lbl_bg_x = label_x - 10
                    lbl_bg_y = label_y - 7
                    out_label_bg = f"[lbg_{i}]"
                    filters.append(
                        f"{current}drawbox="
                        f"x={lbl_bg_x}:y={lbl_bg_y}:"
                        f"w={lbl_bg_w}:h={lbl_bg_h}:"
                        f"color=black@0.5:t=fill"
                        f"{out_label_bg}"
                    )
                    current = out_label_bg

                    out_label = f"[lbl_{i}]"
                    filters.append(
                        f"{current}drawtext="
                        f"text='{label_text}':"
                        f"fontfile={self.FONT_BOLD}:"
                        f"fontsize={self.LABEL_FONT_SIZE}:"
                        f"fontcolor={label_color}:"
                        f"x={label_x}:y={label_y}:"
                        f"shadowcolor=black@0.7:shadowx=1:shadowy=1"
                        f"{out_label}"
                    )
                    current = out_label

        # Finalize
        filters.append(f"{current}null[final]")
        filter_complex = ';'.join(filters)

        cmd = [
            'ffmpeg', '-y', *input_args, '-i', clip['path'],
            '-filter_complex', filter_complex,
            '-map', '[final]',
            '-an',  # Mute original clip audio
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            output
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Listicle clip {clip_index} failed: {stderr.decode()}")
            raise Exception(f"Failed to prepare clip {clip_index + 1}")

        return output

    async def _concat_clips(self, clip_paths: List[str], output_path: str) -> str:
        """Concatenate prepared clips into a single video."""
        if len(clip_paths) == 1:
            shutil.copy2(clip_paths[0], output_path)
            return output_path

        concat_file = os.path.join(self.temp_dir, 'listicle_concat.txt')
        with open(concat_file, 'w') as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-movflags', '+faststart',
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Listicle concat failed: {stderr.decode()}")
            raise Exception("Failed to concatenate clips")

        return output_path

    async def _apply_audio(self, input_path: str, output_path: str) -> str:
        """Add background music to the final video."""
        if not self.background_music or not os.path.exists(self.background_music):
            shutil.copy2(input_path, output_path)
            return output_path

        info = get_media_info(input_path)
        duration = info.get('duration', 0)

        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-i', self.background_music,
            '-filter_complex',
            f"[1:a]aloop=loop=-1:size=2e+09,"
            f"atrim=duration={duration},"
            f"volume={self.bg_music_volume}[music]",
            '-map', '0:v', '-map', '[music]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Listicle audio failed: {stderr.decode()}")
            raise Exception("Failed to add background music")

        return output_path

    async def create(self, output_path: str) -> str:
        """Execute the full listicle creation pipeline.

        Pipeline:
        1. Prepare each clip with all overlays (title, numbers, labels)
        2. Concatenate clips sequentially
        3. Add background music
        4. Finalize with fresh metadata
        """
        if not self.clips:
            raise Exception("No clips added. Add at least one clip.")

        # Step 1: Prepare each clip with overlays
        prepared = []
        for i in range(len(self.clips)):
            logger.info(f"Preparing listicle clip {i + 1}/{len(self.clips)}")
            path = await self._prepare_clip_with_overlays(i)
            prepared.append(path)

        # Step 2: Concatenate
        concat_out = os.path.join(self.temp_dir, f'listicle_concat_{self._random_str()}.mp4')
        await self._concat_clips(prepared, concat_out)

        # Step 3: Add background music
        audio_out = os.path.join(self.temp_dir, f'listicle_audio_{self._random_str()}.mp4')
        await self._apply_audio(concat_out, audio_out)

        # Step 4: Finalize metadata
        cmd = [
            'ffmpeg', '-y', '-i', audio_out,
            '-c', 'copy',
            '-map_metadata', '-1',
            '-metadata', f'creation_time={datetime.utcnow().isoformat()}Z',
            '-metadata', f'encoder=custom_{self._random_str(12)}',
            '-movflags', '+faststart',
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Listicle finalize failed: {stderr.decode()}")
            raise Exception("Failed to finalize video")

        return output_path
