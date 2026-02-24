"""Ranking Video Creator - Auto-builds Top N ranking-style YouTube Shorts.

Uses Pillow for overlay rendering and FFmpeg for video processing.
Clips fill the entire 9:16 frame. Ranking numbers are overlaid on the
left side of the video (not a bottom bar). Title banner at the top.
"""

import os
import asyncio
import random
import string
import shutil
import logging
from typing import List, Tuple, Optional, Dict
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from core.media_info import get_media_info

logger = logging.getLogger(__name__)

FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

COLOR_MAP = {
    'red': '#FF0000', 'white': '#FFFFFF', 'blue': '#0088FF',
    'yellow': '#FFD700', 'green': '#00FF00', 'cyan': '#00FFFF',
    'orange': '#FF8C00', 'pink': '#FF69B4', 'purple': '#9B59B6',
    'neon_green': '#39FF14', 'gold': '#FFD700',
    'gray': '#888888', 'black': '#000000',
}


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return ImageFont.load_default()


def _color(c):
    if c.startswith('#'):
        return c
    return COLOR_MAP.get(c.lower(), '#FFFFFF')


def _hex_to_rgba(hex_color, alpha=255):
    """Convert hex color to RGBA tuple."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, alpha)


class RankingVideoCreator:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        self.title_words = []
        self.clips = []
        self.labels = []
        self.count = 5
        self.background_audio = None
        self.bg_volume = 0.3
        self.mute_clips = False
        self.target_width = 1080
        self.target_height = 1920
        self.title_font_size = 52
        self.number_font_size = 54
        self.label_font_size = 34
        self.highlight_color = '#FF0000'
        self.dim_color = '#555555'
        self.revealed_color = '#FFFFFF'
        self.label_color = '#FFFFFF'

    @staticmethod
    def _rnd(n=8):
        return ''.join(random.choices(
            string.ascii_lowercase + string.digits, k=n))

    def _title_h(self):
        if not self.title_words:
            return 0
        font = _load_font(FONT_BOLD, self.title_font_size)
        text = ' '.join(w for w, _ in self.title_words)
        tmp = Image.new('RGBA', (1, 1))
        d = ImageDraw.Draw(tmp)
        bb = d.textbbox((0, 0), text, font=font)
        tw = bb[2] - bb[0]
        if tw > self.target_width - 80:
            return self.title_font_size * 2 + 90
        return self.title_font_size + 70

    def _draw_title(self, img, draw):
        if not self.title_words:
            return
        th = self._title_h()
        font = _load_font(FONT_BOLD, self.title_font_size)
        draw.rectangle([0, 0, self.target_width, th], fill=(0, 0, 0, 200))

        text = ' '.join(w for w, _ in self.title_words)
        bb = draw.textbbox((0, 0), text, font=font)
        tw = bb[2] - bb[0]
        mw = self.target_width - 80

        if tw <= mw:
            x = (self.target_width - tw) // 2
            y = (th - self.title_font_size) // 2
            for word, col in self.title_words:
                draw.text((x+2, y+2), word, font=font, fill=(0, 0, 0, 180))
                draw.text((x, y), word, font=font, fill=_color(col))
                wb = draw.textbbox((0, 0), word + ' ', font=font)
                x += wb[2] - wb[0]
        else:
            lines = []
            cur = []
            cw = 0
            for word, col in self.title_words:
                wb = draw.textbbox((0, 0), word + ' ', font=font)
                w = wb[2] - wb[0]
                if cw + w > mw and cur:
                    lines.append(cur)
                    cur = [(word, col)]
                    cw = w
                else:
                    cur.append((word, col))
                    cw += w
            if cur:
                lines.append(cur)
            lh = self.title_font_size + 8
            sy = (th - lh * len(lines)) // 2
            for li, lw in enumerate(lines):
                lt = ' '.join(w for w, _ in lw)
                lb = draw.textbbox((0, 0), lt, font=font)
                x = (self.target_width - (lb[2] - lb[0])) // 2
                y = sy + li * lh
                for word, col in lw:
                    draw.text((x+2, y+2), word, font=font, fill=(0, 0, 0, 180))
                    draw.text((x, y), word, font=font, fill=_color(col))
                    wb = draw.textbbox((0, 0), word + ' ', font=font)
                    x += wb[2] - wb[0]

    def _draw_list(self, img, draw, clip_idx):
        """Draw ranking items overlaid on the left side of the video."""
        nf = _load_font(FONT_BOLD, self.number_font_size)
        lf = _load_font(FONT_REGULAR, self.label_font_size)

        # Layout: items stacked vertically on the left, centered in the video area
        th = self._title_h()
        available_h = self.target_height - th - 80  # 80px bottom margin
        item_h = min(available_h // self.count, self.number_font_size + 40)
        total_h = item_h * self.count
        start_y = th + (available_h - total_h) // 2 + 20

        for i in range(self.count):
            num = self.count - i
            y = start_y + i * item_h
            revealed = i <= clip_idx
            current = i == clip_idx

            if current:
                nc = _color(self.highlight_color)
            elif revealed:
                nc = _color(self.revealed_color)
            else:
                nc = _color(self.dim_color)

            nt = f"{num}."
            # Measure number width for background
            nb = draw.textbbox((0, 0), nt, font=nf)
            nw = nb[2] - nb[0]
            nh = nb[3] - nb[1]

            # Measure label if revealed
            label_text = ""
            lw_px = 0
            if revealed and i < len(self.labels):
                label_text = self.labels[i]
                lb = draw.textbbox((0, 0), label_text, font=lf)
                lw_px = lb[2] - lb[0]

            # Background pill behind number + label
            pill_x = 30
            pill_y = y
            pill_w = nw + 30  # padding around number
            if label_text:
                pill_w = nw + lw_px + 50  # number + gap + label + padding
            pill_h = max(nh, self.label_font_size) + 20

            # Draw semi-transparent rounded background
            if current:
                bg_color = (0, 0, 0, 180)
            elif revealed:
                bg_color = (0, 0, 0, 140)
            else:
                bg_color = (0, 0, 0, 100)

            # Rounded rectangle
            r = 10
            pill_rect = [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h]
            draw.rounded_rectangle(pill_rect, radius=r, fill=bg_color)

            # Draw number
            num_x = pill_x + 12
            num_y = pill_y + (pill_h - nh) // 2
            draw.text((num_x + 2, num_y + 2), nt, font=nf, fill=(0, 0, 0, 200))
            draw.text((num_x, num_y), nt, font=nf, fill=nc)

            # Draw label
            if label_text:
                lc = _color(self.highlight_color if current else self.label_color)
                label_x = num_x + nw + 16
                label_y = pill_y + (pill_h - self.label_font_size) // 2 + 2
                draw.text((label_x + 1, label_y + 1), label_text, font=lf, fill=(0, 0, 0, 200))
                draw.text((label_x, label_y), label_text, font=lf, fill=lc)
            elif not revealed:
                # Dim line placeholder
                line_x = num_x + nw + 16
                line_y = pill_y + pill_h // 2
                draw.line([(line_x, line_y), (line_x + 120, line_y)],
                          fill=(80, 80, 80, 150), width=2)

    def generate_overlay(self, clip_idx):
        img = Image.new('RGBA', (self.target_width, self.target_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        self._draw_title(img, draw)
        self._draw_list(img, draw, clip_idx)
        out = os.path.join(self.temp_dir, f'ov_{clip_idx}_{self._rnd()}.png')
        img.save(out, 'PNG')
        return out

    async def _prepare_clip(self, clip, idx):
        """Prepare a clip: scale and crop to fill the entire 9:16 frame."""
        src = clip['path']
        out = os.path.join(self.temp_dir, f'p_{idx}_{self._rnd()}.mp4')
        ia = []
        if clip.get('start', 0) > 0:
            ia += ['-ss', str(clip['start'])]
        if clip.get('end'):
            ia += ['-to', str(clip['end'])]

        w = self.target_width
        h = self.target_height

        # Scale up to fill frame (crop overflow) instead of letterboxing
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
              f"crop={w}:{h},setsar=1")

        cmd = ['ffmpeg', '-y', *ia, '-i', src, '-vf', vf,
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
               '-r', '30', '-pix_fmt', 'yuv420p']

        info = get_media_info(src)
        if self.mute_clips or not info.get('has_audio'):
            cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                    '-shortest', '-c:a', 'aac', '-b:a', '128k']
        else:
            cmd += ['-c:a', 'aac', '-ar', '44100', '-b:a', '192k']
        cmd.append(out)

        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await p.communicate()
        if p.returncode != 0:
            raise Exception(f"Clip {idx} failed: {err.decode()[-300:]}")
        return out

    async def _concat(self, paths, output):
        if len(paths) == 1:
            shutil.copy2(paths[0], output)
            return
        cf = os.path.join(self.temp_dir, 'concat.txt')
        with open(cf, 'w') as f:
            for p in paths:
                f.write(f"file '{p}'\n")
        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', cf,
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
               '-c:a', 'aac', '-ar', '44100', '-b:a', '192k',
               '-pix_fmt', 'yuv420p', output]
        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await p.communicate()
        if p.returncode != 0:
            raise Exception(f"Concat failed: {err.decode()[-300:]}")

    async def _overlay(self, video, output, ovs, durs):
        inputs = ['-i', video]
        for o in ovs:
            inputs += ['-i', o]
        ts = []
        t = 0.0
        for d in durs:
            ts.append((t, t + d))
            t += d
        parts = []
        cur = "[0:v]"
        for i, (s, e) in enumerate(ts):
            ol = f"[ov{i}]"
            en = f"between(t,{s:.3f},{e:.3f})" if i < len(ts)-1 else f"gte(t,{s:.3f})"
            parts.append(f"{cur}[{i+1}:v]overlay=0:0:enable='{en}'{ol}")
            cur = ol
        parts.append(f"{cur}null[final]")
        cmd = ['ffmpeg', '-y', *inputs, '-filter_complex', ';'.join(parts),
               '-map', '[final]', '-map', '0:a?',
               '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
               '-c:a', 'copy', '-pix_fmt', 'yuv420p', '-r', '30', output]
        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await p.communicate()
        if p.returncode != 0:
            raise Exception(f"Overlay failed: {err.decode()[-300:]}")

    async def _mix_audio(self, video, output):
        if not self.background_audio or not os.path.exists(self.background_audio):
            shutil.copy2(video, output)
            return
        info = get_media_info(video)
        dur = info.get('duration', 30)

        # Normalize both audio streams to same sample rate before mixing
        cmd = ['ffmpeg', '-y', '-i', video, '-i', self.background_audio,
               '-filter_complex',
               f"[0:a]aresample=44100[clip];"
               f"[1:a]aresample=44100,aloop=loop=-1:size=2e+09,"
               f"atrim=duration={dur},volume={self.bg_volume}[bg];"
               f"[clip][bg]amix=inputs=2:duration=first:normalize=0[out]",
               '-map', '0:v', '-map', '[out]',
               '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', output]
        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await p.communicate()
        if p.returncode != 0:
            logger.warning(f"Audio mix failed, copying without mix: {err.decode()[-200:]}")
            shutil.copy2(video, output)

    async def create(self, output_path, progress_cb=None):
        if not self.clips:
            raise Exception("No clips added.")
        while len(self.labels) < len(self.clips):
            self.labels.append('')

        prepared = []
        for i, c in enumerate(self.clips):
            if progress_cb:
                await progress_cb(f"Processing clip {i+1}/{len(self.clips)}...")
            prepared.append(await self._prepare_clip(c, i))

        if progress_cb:
            await progress_cb("Stitching clips...")
        co = os.path.join(self.temp_dir, f'cat_{self._rnd()}.mp4')
        await self._concat(prepared, co)

        if progress_cb:
            await progress_cb("Generating overlays...")
        durs = []
        for p in prepared:
            info = get_media_info(p)
            durs.append(info.get('duration', 5.0))
        ovs = [self.generate_overlay(i) for i in range(len(self.clips))]

        if progress_cb:
            await progress_cb("Compositing...")
        oo = os.path.join(self.temp_dir, f'ov_{self._rnd()}.mp4')
        await self._overlay(co, oo, ovs, durs)

        if progress_cb:
            await progress_cb("Mixing audio...")
        ao = os.path.join(self.temp_dir, f'au_{self._rnd()}.mp4')
        await self._mix_audio(oo, ao)

        if progress_cb:
            await progress_cb("Finalizing...")
        cmd = ['ffmpeg', '-y', '-i', ao, '-c', 'copy', '-map_metadata', '-1',
               '-metadata', f'creation_time={datetime.utcnow().isoformat()}Z',
               '-metadata', f'encoder=custom_{self._rnd(12)}',
               '-movflags', '+faststart', output_path]
        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await p.communicate()
        return output_path

    def get_config(self):
        return {
            'type': 'ranking', 'title_words': self.title_words,
            'count': self.count, 'labels': self.labels,
            'mute_clips': self.mute_clips, 'bg_volume': self.bg_volume,
            'highlight_color': self.highlight_color,
        }

    def load_config(self, cfg):
        self.title_words = cfg.get('title_words', [])
        self.count = cfg.get('count', 5)
        self.labels = cfg.get('labels', [])
        self.mute_clips = cfg.get('mute_clips', False)
        self.bg_volume = cfg.get('bg_volume', 0.3)
        self.highlight_color = cfg.get('highlight_color', '#FF0000')
