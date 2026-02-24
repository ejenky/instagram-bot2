"""Handlers for the ranking video creation flow.

Flow:
/ranking -> count -> title -> colors -> clips (one by one) -> labels -> audio -> build
"""

import os
import shutil
import tempfile
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    DATA_DIR, WAITING_FOR_CONTENT,
    RANKING_MENU, RANKING_TITLE, RANKING_COLORS,
    RANKING_CLIPS, RANKING_LABELS, RANKING_AUDIO, RANKING_PREVIEW,
)
from core.media_info import get_media_info
from creators.ranking_creator import RankingVideoCreator

logger = logging.getLogger(__name__)


async def ranking_menu(update, context):
    """Show ranking creator menu - choose item count."""
    keyboard = [
        [
            InlineKeyboardButton("Top 3", callback_data="rk_count_3"),
            InlineKeyboardButton("Top 5", callback_data="rk_count_5"),
        ],
        [
            InlineKeyboardButton("Top 7", callback_data="rk_count_7"),
            InlineKeyboardButton("Top 10", callback_data="rk_count_10"),
        ],
        [InlineKeyboardButton("Cancel", callback_data="rk_cancel")],
    ]
    text = (
        "*Ranking Video Creator*\n\n"
        "Auto-build Top N ranking shorts!\n\n"
        "I'll ask you for:\n"
        "1. Title text\n"
        "2. Word colors\n"
        "3. Video clips\n"
        "4. Labels for each item\n"
        "5. Background music (optional)\n\n"
        "How many items in your ranking?"
    )
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif msg:
        await msg.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return RANKING_MENU


async def ranking_menu_handler(update, context):
    """Handle count selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "rk_cancel":
        context.user_data.pop('ranking', None)
        await query.edit_message_text("Cancelled. Send a link or /ranking to start again.")
        return WAITING_FOR_CONTENT

    if query.data.startswith("rk_count_"):
        count = int(query.data.replace("rk_count_", ""))
        context.user_data['ranking'] = {
            'count': count,
            'title_words': [],
            'clips': [],
            'labels': [],
            'temp_dir': tempfile.mkdtemp(prefix='ranking_'),
        }
        await query.edit_message_text(
            f"*Top {count} Ranking*\n\n"
            "Enter your title text:\n"
            "Example: `RANKING TOP 5 LUCKIEST PEOPLE EVER`",
            parse_mode='Markdown'
        )
        return RANKING_TITLE

    return RANKING_MENU


async def ranking_title_handler(update, context):
    """Receive title text, ask for colors."""
    msg = update.message
    if not msg or not msg.text:
        return RANKING_TITLE

    title = msg.text.strip()
    words = title.split()
    rk = context.user_data.get('ranking', {})
    rk['raw_title'] = title
    rk['title_split'] = words

    # Show color assignment instructions
    word_list = ' '.join([f"`{w}`" for w in words])
    await msg.reply_text(
        f"*Title:* {title}\n\n"
        f"Words: {word_list}\n\n"
        "Now assign colors to your words.\n"
        "Format: `{color}WORD WORD {color}WORD...`\n\n"
        "Example:\n"
        "`{red}RANKING {white}TOP 5 {blue}LUCKIEST PEOPLE EVER`\n\n"
        "Available colors: red, white, blue, yellow, green, "
        "cyan, orange, pink, purple, gold\n\n"
        "Or send `default` for all white.",
        parse_mode='Markdown'
    )
    return RANKING_COLORS


async def ranking_colors_handler(update, context):
    """Parse color assignments for title words."""
    msg = update.message
    if not msg or not msg.text:
        return RANKING_COLORS

    text = msg.text.strip()
    rk = context.user_data.get('ranking', {})

    if text.lower() == 'default':
        words = rk.get('title_split', [])
        rk['title_words'] = [(w, 'white') for w in words]
    else:
        # Parse {color}WORD WORD format
        title_words = []
        current_color = 'white'
        parts = text.split()
        for part in parts:
            if part.startswith('{') and '}' in part:
                # Extract color
                color_end = part.index('}')
                current_color = part[1:color_end].lower()
                remaining = part[color_end + 1:]
                if remaining:
                    title_words.append((remaining, current_color))
            else:
                title_words.append((part, current_color))
        rk['title_words'] = title_words

    # Show preview
    preview = ' '.join([f"[{w}:{c}]" for w, c in rk['title_words']])
    count = rk.get('count', 5)

    await msg.reply_text(
        f"*Title colors set!*\n{preview}\n\n"
        f"Now send your clips one at a time.\n"
        f"Clip 1 of {count} (this will be item #{count})\n\n"
        "Send a video file or a social media link.\n"
        "You can also send trim points after each clip.",
        parse_mode='Markdown'
    )
    rk['clips'] = []
    rk['clip_step'] = 'waiting'
    return RANKING_CLIPS


async def ranking_clips_handler(update, context):
    """Handle clip uploads one by one."""
    query = update.callback_query
    msg = update.message
    rk = context.user_data.get('ranking', {})
    count = rk.get('count', 5)
    clips = rk.get('clips', [])

    if query:
        await query.answer()
        action = query.data

        if action == "rk_clip_notrim":
            # Add clip with no trim
            if 'pending_clip' in rk:
                clips.append(rk.pop('pending_clip'))
                rk['clips'] = clips

            got = len(clips)
            if got >= count:
                # All clips received, move to labels
                await query.edit_message_text(
                    f"All {count} clips received!\n\n"
                    f"Now enter labels for each item, one per line.\n"
                    f"Line 1 = item #{count}, Line 2 = item #{count-1}, etc.\n\n"
                    "Example:\n"
                    "`Bad Riding\n"
                    "Axe Throw\n"
                    "Lucky Shot\n"
                    "Close Call\n"
                    "Miracle Save`",
                    parse_mode='Markdown'
                )
                return RANKING_LABELS
            else:
                remaining = count - got
                item_num = count - got
                await query.edit_message_text(
                    f"Clip added! ({got}/{count})\n\n"
                    f"Send clip {got + 1} of {count} (item #{item_num})\n"
                    f"{remaining} clips remaining."
                )
                rk['clip_step'] = 'waiting'
                return RANKING_CLIPS

        elif action == "rk_clip_trim":
            await query.edit_message_text(
                "Enter trim points: `start end`\n"
                "Example: `0 8` (first 8 seconds)\n"
                "Or `3 12` (from 3s to 12s)",
                parse_mode='Markdown'
            )
            rk['clip_step'] = 'trimming'
            return RANKING_CLIPS

        elif action == "rk_cancel":
            context.user_data.pop('ranking', None)
            await query.edit_message_text("Cancelled.")
            return WAITING_FOR_CONTENT

    elif msg:
        step = rk.get('clip_step', 'waiting')

        # Handle trim input
        if step == 'trimming' and msg.text:
            parts = msg.text.strip().split()
            if len(parts) == 2:
                try:
                    s, e = float(parts[0]), float(parts[1])
                    if 'pending_clip' in rk:
                        rk['pending_clip']['start'] = s
                        rk['pending_clip']['end'] = e
                        clips.append(rk.pop('pending_clip'))
                        rk['clips'] = clips

                    got = len(clips)
                    if got >= count:
                        await msg.reply_text(
                            f"All {count} clips received!\n\n"
                            f"Now enter labels, one per line.\n"
                            f"Line 1 = item #{count}, Line 2 = item #{count-1}, etc.\n\n"
                            "Example:\n"
                            "Bad Riding\n"
                            "Axe Throw\n"
                            "Lucky Shot",
                        )
                        return RANKING_LABELS

                    remaining = count - got
                    item_num = count - got
                    await msg.reply_text(
                        f"Trimmed! ({got}/{count})\n"
                        f"Send clip {got + 1} of {count} (item #{item_num})")
                    rk['clip_step'] = 'waiting'
                    return RANKING_CLIPS
                except ValueError:
                    await msg.reply_text("Invalid. Use: `0 8`", parse_mode='Markdown')
                    return RANKING_CLIPS
            await msg.reply_text("Invalid. Use: `start end`", parse_mode='Markdown')
            return RANKING_CLIPS

        # Handle video upload
        if msg.video or msg.document:
            file = await (msg.video or msg.document).get_file()
            ext = 'mp4'
            if msg.document and msg.document.file_name:
                ext = msg.document.file_name.split('.')[-1]
            path = os.path.join(DATA_DIR, f'rk_clip_{msg.from_user.id}_{len(clips)}.{ext}')
            await file.download_to_drive(path)

            info = get_media_info(path)
            dur = info.get('duration', 0)

            rk['pending_clip'] = {'path': path, 'start': 0, 'end': None}
            rk['clip_step'] = 'config'

            keyboard = [
                [InlineKeyboardButton("Use Full Clip", callback_data="rk_clip_notrim")],
                [InlineKeyboardButton("Trim", callback_data="rk_clip_trim")],
            ]
            await msg.reply_text(
                f"Clip received! Duration: {dur:.1f}s\n"
                f"({len(clips) + 1}/{count})",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return RANKING_CLIPS

        # Handle link
        if msg.text:
            text = msg.text.strip()
            from core.downloader import MediaDownloader
            if MediaDownloader.is_supported_url(text):
                await msg.reply_text("Downloading...")
                try:
                    with tempfile.TemporaryDirectory() as td:
                        dl = MediaDownloader(td)
                        result = await dl.download(text)
                        path = os.path.join(
                            DATA_DIR, f'rk_clip_{msg.from_user.id}_{len(clips)}.mp4')
                        shutil.copy2(result['path'], path)

                    info = get_media_info(path)
                    dur = info.get('duration', 0)
                    rk['pending_clip'] = {'path': path, 'start': 0, 'end': None}
                    rk['clip_step'] = 'config'

                    keyboard = [
                        [InlineKeyboardButton("Use Full Clip", callback_data="rk_clip_notrim")],
                        [InlineKeyboardButton("Trim", callback_data="rk_clip_trim")],
                    ]
                    await msg.reply_text(
                        f"Downloaded! Duration: {dur:.1f}s\n"
                        f"({len(clips) + 1}/{count})",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    await msg.reply_text(f"Download failed: {e}\nTry again or upload directly.")
                return RANKING_CLIPS

            await msg.reply_text("Send a video file or social media link.")
            return RANKING_CLIPS

    return RANKING_CLIPS


async def ranking_labels_handler(update, context):
    """Receive labels for each ranking item."""
    msg = update.message
    if not msg or not msg.text:
        return RANKING_LABELS

    rk = context.user_data.get('ranking', {})
    count = rk.get('count', 5)

    lines = [l.strip() for l in msg.text.strip().split('\n') if l.strip()]

    # Pad or trim to count
    while len(lines) < count:
        lines.append(f"Item {count - len(lines)}")
    lines = lines[:count]

    rk['labels'] = lines

    preview = '\n'.join([f"  {count - i}. {l}" for i, l in enumerate(lines)])

    keyboard = [
        [InlineKeyboardButton("Add Background Music", callback_data="rk_audio_add")],
        [InlineKeyboardButton("Skip (No Music)", callback_data="rk_audio_skip")],
        [InlineKeyboardButton("Mute Clip Audio", callback_data="rk_audio_mute")],
    ]
    await msg.reply_text(
        f"*Labels set!*\n\n{preview}\n\n"
        "Want to add background music?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return RANKING_AUDIO


async def ranking_audio_handler(update, context):
    """Handle audio settings."""
    query = update.callback_query
    msg = update.message
    rk = context.user_data.get('ranking', {})

    if query:
        await query.answer()
        action = query.data

        if action == "rk_audio_skip":
            return await _build_ranking(update, context)

        elif action == "rk_audio_add":
            await query.edit_message_text(
                "Send an audio file for background music.\n"
                "Or send /skip to build without music."
            )
            return RANKING_AUDIO

        elif action == "rk_audio_mute":
            rk['mute_clips'] = True
            keyboard = [
                [InlineKeyboardButton("Add Background Music", callback_data="rk_audio_add")],
                [InlineKeyboardButton("Build Without Music", callback_data="rk_audio_skip")],
            ]
            await query.edit_message_text(
                "Clip audio will be muted.\n"
                "Add background music?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return RANKING_AUDIO

    elif msg:
        if msg.text and msg.text.strip() == '/skip':
            return await _build_ranking(update, context)

        if msg.audio or msg.voice or msg.document:
            file = await (msg.audio or msg.voice or msg.document).get_file()
            ext = 'mp3'
            if msg.document and msg.document.file_name:
                ext = msg.document.file_name.split('.')[-1]
            path = os.path.join(DATA_DIR, f'rk_audio_{msg.from_user.id}.{ext}')
            await file.download_to_drive(path)
            rk['background_audio'] = path
            await msg.reply_text("Background music set!")
            return await _build_ranking(update, context)

    return RANKING_AUDIO


async def _build_ranking(update, context):
    """Build the ranking video."""
    rk = context.user_data.get('ranking', {})
    msg_obj = update.callback_query.message if update.callback_query else update.message

    status = await msg_obj.reply_text("Building ranking video...\nThis may take a moment.")

    try:
        td = rk.get('temp_dir', tempfile.mkdtemp(prefix='ranking_'))
        creator = RankingVideoCreator(td)
        creator.count = rk.get('count', 5)
        creator.title_words = rk.get('title_words', [])
        creator.clips = rk.get('clips', [])
        creator.labels = rk.get('labels', [])
        creator.mute_clips = rk.get('mute_clips', False)

        if rk.get('background_audio'):
            creator.background_audio = rk['background_audio']
            creator.bg_volume = 0.3

        output = os.path.join(td, f'ranking_{creator._rnd()}.mp4')

        async def progress(text):
            try:
                await status.edit_text(f"Building...\n{text}")
            except Exception:
                pass

        await creator.create(output, progress_cb=progress)

        await status.edit_text("Uploading...")
        with open(output, 'rb') as f:
            await msg_obj.reply_video(
                video=f,
                caption=(
                    f"Ranking video created!\n"
                    f"{creator.count} items | "
                    f"{len(creator.clips)} clips"
                ),
                supports_streaming=True
            )

        await status.delete()

        keyboard = [
            [InlineKeyboardButton("Create Another", callback_data="rk_new")],
            [InlineKeyboardButton("Done", callback_data="rk_done")],
        ]
        await msg_obj.reply_text(
            "What next?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return RANKING_PREVIEW

    except Exception as e:
        logger.error(f"Ranking build failed: {e}", exc_info=True)
        await status.edit_text(f"Build failed: {e}")
        keyboard = [
            [InlineKeyboardButton("Try Again", callback_data="rk_new")],
            [InlineKeyboardButton("Cancel", callback_data="rk_done")],
        ]
        await msg_obj.reply_text(
            "Something went wrong.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return RANKING_PREVIEW


async def ranking_preview_handler(update, context):
    """Handle post-build actions."""
    query = update.callback_query
    await query.answer()

    if query.data == "rk_new":
        context.user_data.pop('ranking', None)
        return await ranking_menu(update, context)
    elif query.data == "rk_done":
        # Cleanup
        rk = context.user_data.pop('ranking', {})
        td = rk.get('temp_dir')
        if td and os.path.exists(td):
            shutil.rmtree(td, ignore_errors=True)
        await query.edit_message_text("Done! Send a link or /ranking to make another.")
        return WAITING_FOR_CONTENT

    return RANKING_PREVIEW
