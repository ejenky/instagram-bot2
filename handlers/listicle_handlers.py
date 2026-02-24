"""Handlers for the listicle/ranking video creation flow."""

import os
import shutil
import tempfile
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    DATA_DIR, WAITING_FOR_CONTENT,
    LISTICLE_TITLE, LISTICLE_CLIPS, LISTICLE_LABELS,
    LISTICLE_MUSIC, LISTICLE_CONFIRM,
)
from core.media_info import get_media_info
from creators.listicle_creator import ListicleCreator

logger = logging.getLogger(__name__)


def _get_listicle(context: ContextTypes.DEFAULT_TYPE) -> ListicleCreator:
    """Get or create the ListicleCreator in user context."""
    if 'listicle' not in context.user_data:
        context.user_data['listicle'] = ListicleCreator(
            tempfile.mkdtemp(prefix='listicle_')
        )
    return context.user_data['listicle']


async def listicle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the listicle creation flow."""
    # Reset any existing listicle state
    context.user_data.pop('listicle', None)
    _get_listicle(context)

    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if update.callback_query:
        await update.callback_query.answer()

    text = (
        "*Listicle / Ranking Video Creator*\n\n"
        "Create a CapCut-style ranking video with:\n"
        "- Title bar at top with colored text\n"
        "- Numbered list on the left side\n"
        "- Labels that reveal as clips play\n"
        "- Background music\n\n"
        "*Step 1: Enter your title*\n\n"
        "Send one segment per line as `text | color`\n\n"
        "*Example:*\n"
        "`RANKING | red`\n"
        "`TOP 5 | white`\n"
        "`LUCKIEST PEOPLE EVER | blue`\n\n"
        "*Colors:* red, white, blue, yellow, green, cyan, pink, orange, purple\n\n"
        "Or just send plain text for a white title."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    elif msg:
        await msg.reply_text(text, parse_mode='Markdown')

    return LISTICLE_TITLE


async def listicle_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle title input."""
    msg = update.message
    if not msg or not msg.text:
        return LISTICLE_TITLE

    text = msg.text.strip()
    if text.startswith('/'):
        if text == '/cancel':
            context.user_data.pop('listicle', None)
            await msg.reply_text("Listicle cancelled.")
            return WAITING_FOR_CONTENT
        return LISTICLE_TITLE

    listicle = _get_listicle(context)

    # Parse title segments: "text | color" per line
    segments = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if '|' in line:
            parts = line.split('|', 1)
            seg_text = parts[0].strip()
            seg_color = parts[1].strip().lower() if len(parts) > 1 else 'white'
        else:
            seg_text = line
            seg_color = 'white'
        if seg_text:
            segments.append((seg_text, seg_color))

    if not segments:
        await msg.reply_text("No title text found. Please send at least one line of text.")
        return LISTICLE_TITLE

    listicle.set_title(segments)

    # Show confirmation and move to clips
    title_preview = " ".join(f"*{t}* ({c})" for t, c in segments)
    await msg.reply_text(
        f"Title set: {title_preview}\n\n"
        "*Step 2: Send your video clips*\n\n"
        "Upload video files one at a time. These will play in order "
        "(clip 1 = item #1, clip 2 = item #2, etc.)\n\n"
        "You can also send social media links to download clips.\n\n"
        "Send /done when you've added all clips.",
        parse_mode='Markdown'
    )
    return LISTICLE_CLIPS


async def listicle_clips_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle clip uploads for the listicle."""
    query = update.callback_query
    msg = update.message
    listicle = _get_listicle(context)

    if query:
        await query.answer()
        return LISTICLE_CLIPS

    if not msg:
        return LISTICLE_CLIPS

    # Text messages (commands or links)
    if msg.text:
        text = msg.text.strip()

        if text == '/done':
            if not listicle.clips:
                await msg.reply_text("No clips added yet. Send at least one video clip.")
                return LISTICLE_CLIPS

            clip_count = len(listicle.clips)
            await msg.reply_text(
                f"Got *{clip_count}* clips!\n\n"
                f"*Step 3: Enter labels* (one per line, one for each clip)\n\n"
                f"Send {clip_count} labels, one per line.\n\n"
                "*Example:*\n"
                "`Bad Riding`\n"
                "`Axe Throw`\n"
                "`Close Call`\n"
                "`Lucky Save`\n"
                "`Perfect Timing`\n\n"
                "Emojis in labels will be stripped for video rendering.",
                parse_mode='Markdown'
            )
            return LISTICLE_LABELS

        if text == '/cancel':
            context.user_data.pop('listicle', None)
            await msg.reply_text("Listicle cancelled.")
            return WAITING_FOR_CONTENT

        # Try as URL download
        from core.downloader import MediaDownloader
        if MediaDownloader.is_supported_url(text):
            await msg.reply_text("Downloading clip...")
            try:
                with tempfile.TemporaryDirectory() as td:
                    downloader = MediaDownloader(td)
                    result = await downloader.download(text)
                    persistent = os.path.join(
                        DATA_DIR,
                        f'listicle_clip_{msg.from_user.id}_{len(listicle.clips)}.mp4'
                    )
                    shutil.copy2(result['path'], persistent)

                listicle.add_clip(persistent)
                info = get_media_info(persistent)
                duration = info.get('duration', 0)

                await msg.reply_text(
                    f"Clip {len(listicle.clips)} added! Duration: {duration:.1f}s\n"
                    f"Total clips: {len(listicle.clips)}\n\n"
                    "Send another clip or /done to continue."
                )
            except Exception as e:
                await msg.reply_text(f"Download failed: {e}")
            return LISTICLE_CLIPS

        await msg.reply_text("Send a video file, a social media link, or /done when finished.")
        return LISTICLE_CLIPS

    # Video file upload
    if msg.video or msg.document:
        file = await (msg.video or msg.document).get_file()
        ext = 'mp4'
        if msg.document and msg.document.file_name:
            ext = msg.document.file_name.split('.')[-1]
        path = os.path.join(
            DATA_DIR,
            f'listicle_clip_{msg.from_user.id}_{len(listicle.clips)}.{ext}'
        )
        await file.download_to_drive(path)

        listicle.add_clip(path)
        info = get_media_info(path)
        duration = info.get('duration', 0)

        await msg.reply_text(
            f"Clip {len(listicle.clips)} added! Duration: {duration:.1f}s\n"
            f"Total clips: {len(listicle.clips)}\n\n"
            "Send another clip or /done to continue."
        )
        return LISTICLE_CLIPS

    await msg.reply_text("Send a video file or /done when finished.")
    return LISTICLE_CLIPS


async def listicle_labels_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle label input for the listicle."""
    msg = update.message
    if not msg or not msg.text:
        return LISTICLE_LABELS

    text = msg.text.strip()
    if text == '/cancel':
        context.user_data.pop('listicle', None)
        await msg.reply_text("Listicle cancelled.")
        return WAITING_FOR_CONTENT

    listicle = _get_listicle(context)
    clip_count = len(listicle.clips)

    # Parse labels (one per line)
    labels = [line.strip() for line in text.split('\n') if line.strip()]

    if len(labels) < clip_count:
        await msg.reply_text(
            f"Need {clip_count} labels (one per clip), but got {len(labels)}.\n"
            f"Send {clip_count} labels, one per line."
        )
        return LISTICLE_LABELS

    # Trim to clip count
    labels = labels[:clip_count]
    listicle.set_labels(labels)

    label_preview = "\n".join(f"  {i + 1}. {l}" for i, l in enumerate(labels))
    await msg.reply_text(
        f"Labels set:\n{label_preview}\n\n"
        "*Step 4: Background music*\n\n"
        "Send an audio file for background music,\n"
        "or /skip to create without music.",
        parse_mode='Markdown'
    )
    return LISTICLE_MUSIC


async def listicle_music_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle background music upload or skip."""
    msg = update.message
    if not msg:
        return LISTICLE_MUSIC

    listicle = _get_listicle(context)

    if msg.text:
        text = msg.text.strip()
        if text == '/cancel':
            context.user_data.pop('listicle', None)
            await msg.reply_text("Listicle cancelled.")
            return WAITING_FOR_CONTENT

        if text == '/skip':
            return await _show_listicle_confirm(msg, listicle)

        await msg.reply_text("Send an audio file or /skip to continue without music.")
        return LISTICLE_MUSIC

    # Audio file upload
    if msg.audio or msg.voice or msg.document:
        file = await (msg.audio or msg.voice or msg.document).get_file()
        ext = 'mp3'
        if msg.document and msg.document.file_name:
            ext = msg.document.file_name.split('.')[-1]
        path = os.path.join(DATA_DIR, f'listicle_music_{msg.from_user.id}.{ext}')
        await file.download_to_drive(path)

        listicle.set_background_music(path)
        await msg.reply_text("Background music set!")
        return await _show_listicle_confirm(msg, listicle)

    await msg.reply_text("Send an audio file or /skip.")
    return LISTICLE_MUSIC


async def _show_listicle_confirm(msg, listicle: ListicleCreator) -> int:
    """Show the build confirmation summary."""
    title_text = " ".join(t for t, _ in listicle.title_segments)
    labels_text = ", ".join(listicle.labels) if listicle.labels else "None"
    music_text = "Yes" if listicle.background_music else "No"

    keyboard = [
        [InlineKeyboardButton("Build Video", callback_data="listicle_build")],
        [
            InlineKeyboardButton("Edit Title", callback_data="listicle_edit_title"),
            InlineKeyboardButton("Edit Labels", callback_data="listicle_edit_labels"),
        ],
        [
            InlineKeyboardButton("Music Volume", callback_data="listicle_volume"),
            InlineKeyboardButton("Cancel", callback_data="listicle_cancel"),
        ],
    ]

    await msg.reply_text(
        f"*Ready to build!*\n\n"
        f"*Title:* {title_text}\n"
        f"*Clips:* {len(listicle.clips)}\n"
        f"*Labels:* {labels_text}\n"
        f"*Music:* {music_text}\n"
        f"*Music volume:* {listicle.bg_music_volume}\n"
        f"*Output:* 1080x1920 (9:16)\n",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return LISTICLE_CONFIRM


async def listicle_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the confirm/build step."""
    query = update.callback_query
    if not query:
        return LISTICLE_CONFIRM

    await query.answer()
    action = query.data
    listicle = _get_listicle(context)

    if action == "listicle_build":
        return await _build_listicle(query, context, listicle)

    elif action == "listicle_edit_title":
        await query.edit_message_text(
            "*Edit title:*\n\nSend title segments as `text | color`, one per line.",
            parse_mode='Markdown'
        )
        return LISTICLE_TITLE

    elif action == "listicle_edit_labels":
        clip_count = len(listicle.clips)
        await query.edit_message_text(
            f"*Edit labels:*\n\nSend {clip_count} labels, one per line.",
            parse_mode='Markdown'
        )
        return LISTICLE_LABELS

    elif action == "listicle_volume":
        keyboard = [
            [
                InlineKeyboardButton("0.1", callback_data="listvol_0.1"),
                InlineKeyboardButton("0.2", callback_data="listvol_0.2"),
                InlineKeyboardButton("0.3", callback_data="listvol_0.3"),
            ],
            [
                InlineKeyboardButton("0.5", callback_data="listvol_0.5"),
                InlineKeyboardButton("0.7", callback_data="listvol_0.7"),
                InlineKeyboardButton("1.0", callback_data="listvol_1.0"),
            ],
        ]
        await query.edit_message_text(
            "Select background music volume:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return LISTICLE_CONFIRM

    elif action.startswith("listvol_"):
        vol = float(action.replace("listvol_", ""))
        listicle.bg_music_volume = vol
        if listicle.background_music:
            listicle.set_background_music(listicle.background_music, vol)
        return await _show_listicle_confirm(query.message, listicle)

    elif action == "listicle_cancel":
        context.user_data.pop('listicle', None)
        await query.edit_message_text("Listicle cancelled. Send a link or /create to start over.")
        return WAITING_FOR_CONTENT

    # Post-build actions
    elif action == "listicle_new":
        context.user_data.pop('listicle', None)
        return await listicle_start(update, context)

    elif action == "listicle_done":
        context.user_data.pop('listicle', None)
        await query.edit_message_text("Done! Send a link or /create for a new video.")
        return WAITING_FOR_CONTENT

    return LISTICLE_CONFIRM


async def _build_listicle(query, context, listicle: ListicleCreator) -> int:
    """Build the listicle video and send it."""
    msg = query.message
    status = await msg.reply_text(
        f"Building listicle video...\n"
        f"Processing {len(listicle.clips)} clips with overlays..."
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            listicle.temp_dir = temp_dir
            output_path = os.path.join(temp_dir, f'listicle_{listicle._random_str()}.mp4')

            await listicle.create(output_path)

            await status.edit_text("Uploading video...")
            with open(output_path, 'rb') as f:
                title_text = " ".join(t for t, _ in listicle.title_segments)
                await msg.reply_video(
                    video=f,
                    caption=(
                        f"Listicle: {title_text}\n"
                        f"Clips: {len(listicle.clips)} | "
                        f"Labels: {len(listicle.labels)} | "
                        f"1080x1920"
                    ),
                    supports_streaming=True
                )

        await status.delete()

        keyboard = [
            [InlineKeyboardButton("Create Another", callback_data="listicle_new")],
            [InlineKeyboardButton("Done", callback_data="listicle_done")],
        ]
        await msg.reply_text(
            "Listicle video created!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return LISTICLE_CONFIRM

    except Exception as e:
        logger.error(f"Listicle build failed: {e}", exc_info=True)
        await status.edit_text(f"Build failed: {e}")

        keyboard = [
            [InlineKeyboardButton("Try Again", callback_data="listicle_build")],
            [InlineKeyboardButton("Cancel", callback_data="listicle_cancel")],
        ]
        await msg.reply_text(
            "Something went wrong. Try again or cancel.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return LISTICLE_CONFIRM
