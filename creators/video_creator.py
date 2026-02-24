"""Video creator - CapCut-like video creation from clips, text, audio."""

import os
import asyncio
import random
import string
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime

from core.media_info import get_media_info

logger = logging.getLogger(__name__)


class TextStyle:
    """Represents a text overlay style configuration."""

    # Available font families (mapped to system paths)
    FONTS = {
        'bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'regular': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'condensed': '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
        'mono': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
        'serif': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
    }

    # Color presets
    COLORS = {
        'white': 'white',
        'black': 'black',
        'red': '#FF0000',
        'yellow': '#FFD700',
        'green': '#00FF00',
        'blue': '#0088FF',
        'pink': '#FF69B4',
        'orange': '#FF8C00',
        'purple': '#9B59B6',
        'cyan': '#00FFFF',
        'neon_green': '#39FF14',
        'neon_pink': '#FF1493',
    }

    def __init__(
        self,
        text: str,
        font: str = 'bold',
        size: int = 58,
        color: str = 'white',
        position: str = 'center',  # center, top, bottom, custom
        x: Optional[int] = None,
        y: Optional[int] = None,
        shadow: bool = True,
        shadow_color: str = 'black@0.7',
        outline: bool = False,
        outline_color: str = 'black',
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        animation: str = 'none',  # none, fade_in, fade_out, slide_up
    ):
        self.text = text
        self.font = font
        self.size = size
        self.color = color
        self.position = position
        self.x = x
        self.y = y
        self.shadow = shadow
        self.shadow_color = shadow_color
        self.outline = outline
        self.outline_color = outline_color
        self.start_time = start_time
        self.end_time = end_time
        self.animation = animation

    def to_dict(self) -> Dict:
        return {
            'text': self.text, 'font': self.font, 'size': self.size,
            'color': self.color, 'position': self.position,
            'x': self.x, 'y': self.y, 'shadow': self.shadow,
            'start_time': self.start_time, 'end_time': self.end_time,
            'animation': self.animation,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'TextStyle':
        return cls(**{k: v for k, v in d.items() if k in cls.__init__.__code__.co_varnames})


class ClipSegment:
    """Represents a clip segment in the video timeline."""

    def __init__(
        self,
        source_path: str,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        transition: str = 'none',  # none, fade, dissolve, wipe
        transition_duration: float = 0.5,
        speed: float = 1.0,
    ):
        self.source_path = source_path
        self.start_time = start_time
        self.end_time = end_time
        self.transition = transition
        self.transition_duration = transition_duration
        self.speed = speed

    def to_dict(self) -> Dict:
        return {
            'source_path': self.source_path,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'transition': self.transition,
            'transition_duration': self.transition_duration,
            'speed': self.speed,
        }


class VideoCreator:
    """CapCut-like video creator with timeline, text styles, audio, transitions."""

    TRANSITIONS = ['none', 'fade', 'dissolve', 'wipe_left', 'wipe_right', 'zoom']

    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.clips: List[ClipSegment] = []
        self.text_overlays: List[TextStyle] = []
        self.background_audio: Optional[str] = None
        self.bg_audio_volume: float = 0.3
        self.narration_audio: Optional[str] = None
        self.narration_volume: float = 1.0
        self.target_width: int = 1080
        self.target_height: int = 1920
        self.dark_mode: bool = True

    @staticmethod
    def _random_str(length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def add_clip(self, clip: ClipSegment):
        """Add a clip to the timeline."""
        self.clips.append(clip)

    def add_text(self, text_style: TextStyle):
        """Add a text overlay."""
        self.text_overlays.append(text_style)

    def set_background_audio(self, audio_path: str, volume: float = 0.3):
        """Set background music."""
        self.background_audio = audio_path
        self.bg_audio_volume = volume

    def set_narration(self, audio_path: str, volume: float = 1.0):
        """Set narration audio track."""
        self.narration_audio = audio_path
        self.narration_volume = volume

    def clear_timeline(self):
        """Reset the creator."""
        self.clips.clear()
        self.text_overlays.clear()
        self.background_audio = None
        self.narration_audio = None

    def get_config(self) -> Dict:
        """Export current creation config (for template saving)."""
        return {
            'clips': [c.to_dict() for c in self.clips],
            'text_overlays': [t.to_dict() for t in self.text_overlays],
            'background_audio': self.background_audio,
            'bg_audio_volume': self.bg_audio_volume,
            'narration_audio': self.narration_audio,
            'narration_volume': self.narration_volume,
            'target_width': self.target_width,
            'target_height': self.target_height,
            'dark_mode': self.dark_mode,
        }

    async def _prepare_clip(self, clip: ClipSegment, index: int) -> str:
        """Prepare a single clip segment (trim, scale, speed adjust)."""
        info = get_media_info(clip.source_path)
        output = os.path.join(self.temp_dir, f'clip_{index}_{self._random_str()}.mp4')

        filters = []

        # Trim
        input_args = []
        if clip.start_time > 0:
            input_args.extend(['-ss', str(clip.start_time)])
        if clip.end_time is not None:
            input_args.extend(['-to', str(clip.end_time)])

        # Scale to target
        filters.append(
            f"scale={self.target_width}:{self.target_height}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2:"
            f"color={'black' if self.dark_mode else 'white'}"
        )

        # Speed
        if clip.speed != 1.0:
            filters.append(f"setpts={1 / clip.speed}*PTS")

        filter_str = ','.join(filters)

        cmd = [
            'ffmpeg', '-y', *input_args, '-i', clip.source_path,
            '-vf', filter_str,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-pix_fmt', 'yuv420p',
        ]

        if info.get('has_audio'):
            if clip.speed != 1.0:
                cmd.extend(['-af', f'atempo={clip.speed}'])
            cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
        else:
            cmd.extend(['-an'])

        cmd.append(output)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Clip prepare failed: {stderr.decode()}")
            raise Exception(f"Failed to prepare clip {index}")

        return output

    async def _concat_clips(self, clip_paths: List[str], output_path: str) -> str:
        """Concatenate prepared clips into one video."""
        if len(clip_paths) == 1:
            # Just copy
            import shutil
            shutil.copy2(clip_paths[0], output_path)
            return output_path

        # Create concat file
        concat_file = os.path.join(self.temp_dir, 'concat.txt')
        with open(concat_file, 'w') as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
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
            logger.error(f"Concat failed: {stderr.decode()}")
            raise Exception("Failed to concatenate clips")

        return output_path

    async def _apply_text_overlays(self, input_path: str, output_path: str) -> str:
        """Apply text overlays to the video."""
        if not self.text_overlays:
            import shutil
            shutil.copy2(input_path, output_path)
            return output_path

        filter_parts = []
        current = "[0:v]"

        for i, text in enumerate(self.text_overlays):
            font_path = TextStyle.FONTS.get(text.font, TextStyle.FONTS['bold'])
            color = TextStyle.COLORS.get(text.color, text.color)

            escaped = text.text.replace("'", "'\\''").replace(":", "\\:").replace("\\", "\\\\")

            # Position
            if text.position == 'center':
                x_expr = "(w-text_w)/2"
                y_expr = "(h-text_h)/2"
            elif text.position == 'top':
                x_expr = "(w-text_w)/2"
                y_expr = "50"
            elif text.position == 'bottom':
                x_expr = "(w-text_w)/2"
                y_expr = "h-text_h-50"
            else:
                x_expr = str(text.x or 0)
                y_expr = str(text.y or 0)

            out_label = f"[t{i}]"

            drawtext = (
                f"{current}drawtext="
                f"text='{escaped}':"
                f"fontfile={font_path}:"
                f"fontsize={text.size}:"
                f"fontcolor={color}:"
                f"x={x_expr}:y={y_expr}"
            )

            if text.shadow:
                drawtext += f":shadowcolor={text.shadow_color}:shadowx=2:shadowy=2"

            if text.outline:
                drawtext += f":borderw=2:bordercolor={text.outline_color}"

            # Timing
            if text.start_time > 0 or text.end_time is not None:
                enable_parts = []
                if text.start_time > 0:
                    enable_parts.append(f"gte(t\\,{text.start_time})")
                if text.end_time is not None:
                    enable_parts.append(f"lte(t\\,{text.end_time})")
                enable_expr = '*'.join(enable_parts)
                drawtext += f":enable='{enable_expr}'"

            # Animation
            if text.animation == 'fade_in':
                drawtext += f":alpha='if(lt(t\\,{text.start_time + 0.5})\\,(t-{text.start_time})/0.5\\,1)'"
            elif text.animation == 'fade_out' and text.end_time:
                fade_start = text.end_time - 0.5
                drawtext += f":alpha='if(gt(t\\,{fade_start})\\,({text.end_time}-t)/0.5\\,1)'"

            drawtext += out_label
            filter_parts.append(drawtext)
            current = out_label

        filter_parts.append(f"{current}null[final]")
        filter_complex = ';'.join(filter_parts)

        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-filter_complex', filter_complex,
            '-map', '[final]', '-map', '0:a?',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-c:a', 'copy',
            '-pix_fmt', 'yuv420p',
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Text overlay failed: {stderr.decode()}")
            raise Exception("Failed to apply text overlays")

        return output_path

    async def _apply_audio(self, input_path: str, output_path: str) -> str:
        """Mix in background audio and/or narration."""
        if not self.background_audio and not self.narration_audio:
            import shutil
            shutil.copy2(input_path, output_path)
            return output_path

        # Get video duration
        info = get_media_info(input_path)
        duration = info.get('duration', 0)

        inputs = ['-i', input_path]
        filter_parts = []
        audio_idx = 1

        if self.background_audio and os.path.exists(self.background_audio):
            inputs.extend(['-i', self.background_audio])
            # Loop and trim background music to video duration, adjust volume
            filter_parts.append(
                f"[{audio_idx}:a]aloop=loop=-1:size=2e+09,"
                f"atrim=duration={duration},"
                f"volume={self.bg_audio_volume}[bg_audio]"
            )
            audio_idx += 1

        if self.narration_audio and os.path.exists(self.narration_audio):
            inputs.extend(['-i', self.narration_audio])
            filter_parts.append(
                f"[{audio_idx}:a]volume={self.narration_volume}[narr_audio]"
            )
            audio_idx += 1

        # Mix audio tracks
        mix_inputs = "[0:a]"
        if self.background_audio and os.path.exists(self.background_audio):
            mix_inputs += "[bg_audio]"
        if self.narration_audio and os.path.exists(self.narration_audio):
            mix_inputs += "[narr_audio]"

        n_inputs = 1  # original audio
        if self.background_audio and os.path.exists(self.background_audio):
            n_inputs += 1
        if self.narration_audio and os.path.exists(self.narration_audio):
            n_inputs += 1

        filter_parts.append(f"{mix_inputs}amix=inputs={n_inputs}:duration=first[mixed_audio]")

        filter_complex = ';'.join(filter_parts)

        cmd = [
            'ffmpeg', '-y', *inputs,
            '-filter_complex', filter_complex,
            '-map', '0:v', '-map', '[mixed_audio]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Audio mix failed: {stderr.decode()}")
            raise Exception("Failed to apply audio")

        return output_path

    async def create(self, output_path: str) -> str:
        """Execute the full creation pipeline.

        Pipeline:
        1. Prepare each clip (trim, scale, speed)
        2. Concatenate clips
        3. Apply text overlays
        4. Mix in audio tracks
        5. Finalize with fresh metadata
        """
        if not self.clips:
            raise Exception("No clips in timeline. Add at least one clip.")

        # Step 1: Prepare clips
        prepared = []
        for i, clip in enumerate(self.clips):
            path = await self._prepare_clip(clip, i)
            prepared.append(path)

        # Step 2: Concatenate
        concat_output = os.path.join(self.temp_dir, f'concat_{self._random_str()}.mp4')
        await self._concat_clips(prepared, concat_output)

        # Step 3: Text overlays
        text_output = os.path.join(self.temp_dir, f'text_{self._random_str()}.mp4')
        await self._apply_text_overlays(concat_output, text_output)

        # Step 4: Audio
        audio_output = os.path.join(self.temp_dir, f'audio_{self._random_str()}.mp4')
        await self._apply_audio(text_output, audio_output)

        # Step 5: Final metadata + copy
        cmd = [
            'ffmpeg', '-y', '-i', audio_output,
            '-c', 'copy',
            '-map_metadata', '-1',
            '-metadata', f'creation_time={datetime.utcnow().isoformat()}Z',
            '-metadata', f'encoder=custom_{self._random_str(12)}',
            '-metadata', f'comment={self._random_str(16)}',
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
            logger.error(f"Final output failed: {stderr.decode()}")
            raise Exception("Failed to finalize video")

        return output_path
