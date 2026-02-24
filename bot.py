"""
Instagram Content Bot v3
- Auto-download from any social media link
- Edit videos/images (metadata reset, smart crop, dimensions, watermark, text)
- Create videos from scratch (CapCut-like: cuts, text styles, audio, transitions)
- Template system for saving and replicating video configurations
"""

import os
import shutil
import logging
import subprocess
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

from core.config import (
    BOT_TOKEN, DATA_DIR, DIMENSION_PRESETS,
    WAITING_FOR_CONTENT, ACTION_CHOICE,
    CHOOSE_CROP, CHOOSE_DIMENSIONS, CHOOSE_MODE,
    ENTER_TEXT, CONFIRM_TEXT, CHOOSE_WATERMARK, ENTER_WATERMARK_TEXT,
    CHOOSE_FILTER, MANAGE_PRESETS, CREATE_PRESET,
    CREATE_MENU, CREATE_ADD_CLIPS, CREATE_TEXT_STYLE,
    CREATE_AUDIO, CREATE_PREVIEW,
    TEMPLATE_MENU, TEMPLATE_NAME, TEMPLATE_DESCRIBE, TEMPLATE_SELECT,
    EDIT_PROMPT,
    RANKING_MENU, RANKING_TITLE, RANKING_COLORS,
    RANKING_CLIPS, RANKING_LABELS, RANKING_AUDIO, RANKING_PREVIEW,
)
from core.downloader import MediaDownloader
from core.media_info import get_media_info

from handlers.edit_handlers import (
    show_crop_options, crop_selected, show_dimensions_options, dimensions_selected,
    mode_selected, text_choice, receive_text, text_confirmed,
    show_watermark_options, watermark_selected, receive_watermark_text,
    show_filter_options, filter_selected, process_content,
)
from handlers.create_handlers import (
    create_menu, create_add_clip_handler, create_text_handler,
    create_audio_handler, create_preview_handler,
)
from handlers.template_handlers import (
    template_menu, template_name_handler, template_describe_handler,
    template_select_handler,
)
from handlers.preset_handlers import (
    manage_presets, preset_action, create_preset,
)
from handlers.ranking_handlers import (
    ranking_menu, ranking_menu_handler, ranking_title_handler,
    ranking_colors_handler, ranking_clips_handler,
    ranking_labels_handler, ranking_audio_handler,
    ranking_preview_handler,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

os.makedirs(DATA_DIR, exist_ok=True)


# ── Core bot handlers ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "*Instagram Content Bot*\n\n"
        "Send me any social media link or upload media directly.\n"
        "I'll auto-download it and let you choose what to do.\n\n"
        "*What I can do:*\n"
        "- Auto-download from any social media platform\n"
        "- Edit videos/images (crop, resize, watermark, text, filters, metadata reset)\n"
        "- Create videos from scratch (cuts, text styles, transitions, audio)\n"
        "- Save & load templates to replicate video styles\n\n"
        "*Commands:*\n"
        "/start - Start the bot\n"
        "/create - Create a video from scratch\n"
        "/ranking - Auto-build ranking shorts (Top 5 etc)\n"
        "/templates - Manage video templates\n"
        "/presets - Manage filter presets\n"
        "/settings - View settings\n"
        "/cancel - Cancel current operation",
        parse_mode='Markdown'
    )
    return WAITING_FOR_CONTENT


async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle incoming content - auto-download links, receive uploads."""
    msg = update.message

    if msg.text:
        url = msg.text.strip()
        if MediaDownloader.is_supported_url(url):
            # Auto-download from any social media link
            await msg.reply_text("Downloading media...")
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    downloader = MediaDownloader(temp_dir)
                    result = await downloader.download(url)

                    # Save to persistent storage
                    ext = os.path.splitext(result['path'])[1] or '.mp4'
                    persistent = os.path.join(DATA_DIR, f'input_{msg.from_user.id}{ext}')
                    shutil.copy2(result['path'], persistent)

                    context.user_data['input_path'] = persistent
                    context.user_data['content_type'] = result['type']
                    context.user_data['media_info'] = get_media_info(persistent)

                info = context.user_data['media_info']
                media_type = context.user_data['content_type']
                duration_str = ""
                if info.get('duration'):
                    duration_str = f"\nDuration: {info['duration']:.1f}s"

                await msg.reply_text(
                    f"Downloaded! ({media_type})\n"
                    f"Resolution: {info.get('width', '?')}x{info.get('height', '?')}"
                    f"{duration_str}"
                )

                # Show edit prompt
                return await show_edit_prompt(update, context)

            except Exception as e:
                await msg.reply_text(f"Download failed: {e}\n\nTry a different link.")
                return WAITING_FOR_CONTENT
        else:
            await msg.reply_text(
                "Send me a link (any social media platform) or upload media directly.\n"
                "Or use /create to make a video from scratch."
            )
            return WAITING_FOR_CONTENT

    elif msg.photo:
        photo = msg.photo[-1]
        file = await photo.get_file()
        path = os.path.join(DATA_DIR, f'input_{msg.from_user.id}.jpg')
        await file.download_to_drive(path)
        context.user_data['input_path'] = path
        context.user_data['content_type'] = 'image'
        context.user_data['media_info'] = get_media_info(path)
        await msg.reply_text("Image received!")
        return await show_edit_prompt(update, context)

    elif msg.video or msg.document:
        file = await (msg.video or msg.document).get_file()
        ext = 'mp4'
        if msg.document and msg.document.file_name:
            ext = msg.document.file_name.split('.')[-1]
        path = os.path.join(DATA_DIR, f'input_{msg.from_user.id}.{ext}')
        await file.download_to_drive(path)
        info = get_media_info(path)
        context.user_data['input_path'] = path
        context.user_data['content_type'] = 'video' if info.get('is_video') else 'image'
        context.user_data['media_info'] = info
        await msg.reply_text(f"{'Video' if info.get('is_video') else 'Image'} received!")
        return await show_edit_prompt(update, context)

    await msg.reply_text("Send a link, video, or image.")
    return WAITING_FOR_CONTENT


async def show_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """After downloading/receiving media, ask if user wants to edit."""
    keyboard = [
        [InlineKeyboardButton("Edit This Media", callback_data="action_edit")],
        [InlineKeyboardButton("Skip (Download Only)", callback_data="action_skip")],
    ]
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "Would you like to edit this media?\n\n"
        "*Edit* includes: smart crop, resize, watermark, text overlay, "
        "filters, metadata reset",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return EDIT_PROMPT


async def edit_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the edit yes/no prompt after download."""
    query = update.callback_query
    await query.answer()

    if query.data == "action_edit":
        await query.edit_message_text("Let's edit your media!")
        return await show_crop_options(update, context)
    elif query.data == "action_skip":
        # Send the raw downloaded file back
        input_path = context.user_data.get('input_path')
        content_type = context.user_data.get('content_type', 'video')
        if input_path and os.path.exists(input_path):
            with open(input_path, 'rb') as f:
                if content_type == 'image':
                    await query.message.reply_photo(photo=f, caption="Here's your downloaded media.")
                else:
                    await query.message.reply_video(video=f, caption="Here's your downloaded media.", supports_streaming=True)
            os.remove(input_path)
        await query.edit_message_text("Done! Send another link or file.")
        context.user_data.clear()
        return WAITING_FOR_CONTENT

    return EDIT_PROMPT


async def action_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle edit vs create choice from main menu."""
    query = update.callback_query
    await query.answer()

    if query.data == "action_edit":
        await query.edit_message_text("Send me a link or upload media to edit.")
        return WAITING_FOR_CONTENT
    elif query.data == "action_create":
        return await create_menu(update, context)

    return ACTION_CHOICE


async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /create command."""
    return await create_menu(update, context)


async def ranking_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /ranking command."""
    return await ranking_menu(update, context)


async def templates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /templates command."""
    return await template_menu(update, context)


async def preview_done_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle actions after video creation preview."""
    query = update.callback_query
    await query.answer()

    if query.data == "create_save_template":
        await query.edit_message_text("Enter a name for this template:")
        context.user_data['template_source'] = 'creator'
        return TEMPLATE_NAME
    elif query.data == "create_new":
        if 'creator' in context.user_data:
            context.user_data['creator'].clear_timeline()
        return await create_menu(update, context)
    elif query.data == "create_done":
        context.user_data.pop('creator', None)
        await query.edit_message_text("Send a link or file to start, or /create for a new video!")
        return WAITING_FOR_CONTENT

    return CREATE_PREVIEW


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from core.config import DEFAULT_WATERMARK_TEXT, WATERMARK_IMAGE_PATH, REEL_WIDTH, REEL_HEIGHT
    dims = "\n".join([f"  {v['label']}" for v in DIMENSION_PRESETS.values()])
    await update.message.reply_text(
        f"*Settings*\n\n"
        f"Default output: {REEL_WIDTH}x{REEL_HEIGHT}\n"
        f"Default watermark: `{DEFAULT_WATERMARK_TEXT}`\n"
        f"Watermark image: {'Set' if os.path.exists(WATERMARK_IMAGE_PATH) else 'Not set'}\n\n"
        f"*Available dimensions:*\n{dims}",
        parse_mode='Markdown'
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Send new content to start.")
    return WAITING_FOR_CONTENT


# ── Main ────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("create", create_command),
            CommandHandler("ranking", ranking_command),
            CommandHandler("templates", templates_command),
            CommandHandler("presets", manage_presets),
            MessageHandler(
                filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                handle_content
            ),
        ],
        states={
            # Content input
            WAITING_FOR_CONTENT: [
                CommandHandler("create", create_command),
                CommandHandler("ranking", ranking_command),
                CommandHandler("templates", templates_command),
                CommandHandler("presets", manage_presets),
                MessageHandler(
                    (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    handle_content
                ),
            ],

            # Edit prompt after download
            EDIT_PROMPT: [
                CallbackQueryHandler(edit_prompt_handler, pattern="^action_"),
            ],

            # Action choice (edit vs create)
            ACTION_CHOICE: [
                CallbackQueryHandler(action_choice_handler, pattern="^action_"),
            ],

            # Editing flow
            CHOOSE_CROP: [
                CallbackQueryHandler(crop_selected, pattern="^crop_"),
            ],
            CHOOSE_DIMENSIONS: [
                CallbackQueryHandler(dimensions_selected, pattern="^dim_"),
            ],
            CHOOSE_MODE: [
                CallbackQueryHandler(mode_selected, pattern="^mode_"),
            ],
            ENTER_TEXT: [
                CallbackQueryHandler(text_choice, pattern="^text_"),
            ],
            CONFIRM_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text),
                CallbackQueryHandler(text_confirmed, pattern="^text_"),
            ],
            CHOOSE_WATERMARK: [
                CallbackQueryHandler(watermark_selected, pattern="^wm_"),
            ],
            ENTER_WATERMARK_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_watermark_text),
            ],
            CHOOSE_FILTER: [
                CallbackQueryHandler(filter_selected, pattern="^filter_"),
            ],

            # Preset management
            MANAGE_PRESETS: [
                CallbackQueryHandler(preset_action),
            ],
            CREATE_PRESET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_preset),
            ],

            # Video creation flow
            CREATE_MENU: [
                CallbackQueryHandler(create_add_clip_handler),
            ],
            CREATE_ADD_CLIPS: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    create_add_clip_handler
                ),
                CallbackQueryHandler(create_add_clip_handler),
            ],
            CREATE_TEXT_STYLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_text_handler),
                CallbackQueryHandler(create_text_handler),
            ],
            CREATE_AUDIO: [
                MessageHandler(
                    (filters.AUDIO | filters.VOICE | filters.Document.ALL | filters.TEXT)
                    & ~filters.COMMAND,
                    create_audio_handler
                ),
                CallbackQueryHandler(create_audio_handler),
            ],
            CREATE_PREVIEW: [
                CallbackQueryHandler(preview_done_handler),
            ],

            # Template management
            TEMPLATE_MENU: [
                CallbackQueryHandler(template_name_handler),
            ],
            TEMPLATE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, template_name_handler),
                CallbackQueryHandler(template_name_handler),
            ],
            TEMPLATE_DESCRIBE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, template_describe_handler),
            ],
            TEMPLATE_SELECT: [
                CallbackQueryHandler(template_select_handler),
            ],

            # Ranking video flow
            RANKING_MENU: [
                CallbackQueryHandler(ranking_menu_handler, pattern="^rk_"),
            ],
            RANKING_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ranking_title_handler),
            ],
            RANKING_COLORS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ranking_colors_handler),
            ],
            RANKING_CLIPS: [
                MessageHandler(
                    filters.TEXT | filters.VIDEO | filters.Document.ALL,
                    ranking_clips_handler
                ),
                CallbackQueryHandler(ranking_clips_handler, pattern="^rk_"),
            ],
            RANKING_LABELS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ranking_labels_handler),
            ],
            RANKING_AUDIO: [
                CommandHandler("skip", ranking_audio_handler),
                MessageHandler(
                    (filters.AUDIO | filters.VOICE | filters.Document.ALL | filters.TEXT)
                    & ~filters.COMMAND,
                    ranking_audio_handler
                ),
                CallbackQueryHandler(ranking_audio_handler, pattern="^rk_"),
            ],
            RANKING_PREVIEW: [
                CallbackQueryHandler(ranking_preview_handler, pattern="^rk_"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("create", create_command),
            CommandHandler("ranking", ranking_command),
            CommandHandler("templates", templates_command),
            CommandHandler("presets", manage_presets),
        ],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("settings", settings))

    print("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
