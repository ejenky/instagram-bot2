"""
Content Bot — CapCut in Telegram
- Auto-download from any social media link (yt-dlp + gallery-dl)
- Full metadata randomization & anti-detection
- Overlays: border, text, retention/sludge filter
- Templates: Reel, Story, Square, Landscape, Slideshow
- AI: Auto-captions (Whisper), TTS voiceover (ElevenLabs), GPT descriptions
- Effects: Speed change, voice effects, background music
- Batch processing, profile scraping, aspect ratio conversion
"""

import os
import re
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
    # New states
    DOWNLOAD_ACTIONS, OVERLAY_MENU, BORDER_COLOR, BORDER_CUSTOM_HEX,
    CAPTION_TEXT, CAPTION_POSITION, CAPTION_STYLE,
    SLUDGE_CATEGORY, SLUDGE_LAYOUT,
    TEMPLATE_CHOICE, ASPECT_CONVERT, ASPECT_METHOD,
    AUTO_CAPTION_STYLE, VOICEOVER_TEXT, VOICEOVER_VOICE, VOICEOVER_MODE,
    SPEED_SELECT, VOICE_EFFECT_SELECT, MUSIC_CATEGORY, MUSIC_SELECT,
    FULL_PROCESS_CONFIRM, SETTINGS_MENU, BATCH_PROCESSING,
    SLIDESHOW_IMAGES, PROFILE_SCRAPE, TEXT_INPUT_ACTION,
    PAGE_SELECT, TWEET_RATIO, TWEET_BG_COLOR, TWEET_XLOGO,
)
from core.downloader import MediaDownloader
from core.media_info import get_media_info

# Existing handlers
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

# New handlers
from handlers.download_handlers import (
    show_download_actions, download_action_handler,
    template_choice_handler, auto_caption_handler,
    full_process_handler, speed_handler, voice_effect_handler,
    music_handler, slideshow_handler, quick_download,
)
from handlers.overlay_handlers import (
    show_overlay_options, overlay_menu_handler,
    border_color_handler, border_custom_hex_handler,
    caption_text_handler, caption_position_handler, caption_style_handler,
    sludge_category_handler, sludge_layout_handler,
    aspect_convert_handler, aspect_method_handler,
)
from handlers.ai_handlers import (
    voiceover_text_handler, voiceover_voice_handler, voiceover_mode_handler,
    handle_text_input, text_input_action_handler,
)
from handlers.settings_handlers import (
    show_settings_menu, settings_handler,
)
from handlers.tweet_handlers import (
    is_tweet_url, show_page_select,
    page_select_handler, tweet_ratio_handler,
    tweet_bg_handler, tweet_xlogo_handler,
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
        "⚡ *Content Bot*\n\n"
        "Send me any social media link or upload media.\n"
        "I'll download it and give you powerful editing options.\n\n"
        "*What I can do:*\n"
        "📥 Download from any platform (TikTok, Instagram, Twitter, YouTube...)\n"
        "🔒 Auto-randomize metadata (anti-detection)\n"
        "🖼️ Overlays: borders, text, retention/sludge filters\n"
        "🎬 Templates: Reel, Story, Square, Landscape, Slideshow\n"
        "📝 Auto-captions (AI transcription + burn)\n"
        "🎤 AI Voiceover (ElevenLabs TTS)\n"
        "🔄 Speed change, voice effects, background music\n"
        "📐 Aspect ratio conversion\n"
        "⚡ One-tap full processing pipeline\n\n"
        "*Commands:*\n"
        "/start - Start\n"
        "/menu - Show feature menu\n"
        "/create - Create video from scratch\n"
        "/ranking - Auto-build ranking shorts\n"
        "/templates - Manage templates\n"
        "/presets - Manage filter presets\n"
        "/settings - Configure defaults\n"
        "/cancel - Cancel current operation",
        parse_mode='Markdown'
    )
    return WAITING_FOR_CONTENT


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show the main feature menu."""
    await update.message.reply_text(
        "📋 *Menu*\n\n"
        "📥 *Download* — Send any social media link\n"
        "🖼️ *Overlay* — Add borders, text, or sludge clips\n"
        "🎬 *Templates* — Format videos for Reels/Shorts/Stories\n"
        "🎤 *Voiceover* — AI-generated narration\n"
        "📝 *Captions* — Auto-transcribe and subtitle\n"
        "⚡ *Quick Process* — One-tap download + randomize\n"
        "⚙️ *Settings* — Default template, voice, caption style\n\n"
        "Just send a link, image, or video to get started!",
        parse_mode='Markdown'
    )
    return WAITING_FOR_CONTENT


async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle incoming content - auto-download links, receive uploads, handle text."""
    msg = update.message

    if msg.text:
        url = msg.text.strip()

        # Tweet URLs get routed to the page selector BEFORE anything else
        if re.search(r'(x\.com|twitter\.com)/\w+/status/\d+', url):
            context.user_data['tw_url'] = url
            return await show_page_select(update, context)

        if MediaDownloader.is_supported_url(url):
            # Check if it's a profile URL
            if MediaDownloader.is_profile_url(url):
                return await handle_profile_url(update, context, url)

            # Auto-download from any social media link
            await msg.reply_text("⏳ Downloading media...")
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    downloader = MediaDownloader(temp_dir)
                    result = await downloader.download(url)

                    if result.get('type') == 'gallery':
                        # Multiple files downloaded (gallery)
                        return await handle_gallery(update, context, result)

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
                    f"✅ Downloaded! ({media_type})\n"
                    f"Resolution: {info.get('width', '?')}x{info.get('height', '?')}"
                    f"{duration_str}"
                )

                # Show action menu (new flow)
                return await show_download_actions(update, context)

            except Exception as e:
                await msg.reply_text(f"❌ Download failed: {e}\n\nTry a different link.")
                return WAITING_FOR_CONTENT
        else:
            # Plain text (not a URL) - offer text actions
            return await handle_text_input(update, context)

    elif msg.photo:
        photo = msg.photo[-1]
        file = await photo.get_file()
        path = os.path.join(DATA_DIR, f'input_{msg.from_user.id}.jpg')
        await file.download_to_drive(path)
        context.user_data['input_path'] = path
        context.user_data['content_type'] = 'image'
        context.user_data['media_info'] = get_media_info(path)
        await msg.reply_text("📸 Image received!")

        # Check if we have a saved caption to auto-apply
        if context.user_data.get('saved_caption'):
            context.user_data['caption_text'] = context.user_data.pop('saved_caption')

        return await show_download_actions(update, context)

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
        await msg.reply_text(f"{'🎬 Video' if info.get('is_video') else '📸 Image'} received!")
        return await show_download_actions(update, context)

    await msg.reply_text("Send a link, video, or image.")
    return WAITING_FOR_CONTENT


async def handle_profile_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> int:
    """Handle profile URL - offer to scrape recent posts."""
    keyboard = [
        [InlineKeyboardButton("📥 Last 10 posts", callback_data="scrape_10")],
        [InlineKeyboardButton("📥 Last 20 posts", callback_data="scrape_20")],
        [InlineKeyboardButton("Cancel", callback_data="scrape_cancel")],
    ]
    context.user_data['profile_url'] = url
    await update.message.reply_text(
        "🔍 *Profile detected!*\n\nHow many recent posts to download?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return PROFILE_SCRAPE


async def profile_scrape_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle profile scraping."""
    query = update.callback_query
    await query.answer()

    if query.data == 'scrape_cancel':
        await query.edit_message_text("Cancelled.")
        context.user_data.clear()
        return WAITING_FOR_CONTENT

    count = int(query.data.replace('scrape_', ''))
    url = context.user_data.get('profile_url', '')

    await query.edit_message_text(f"⏳ Scraping last {count} posts from profile...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = MediaDownloader(temp_dir)
            results = await downloader.download_profile(url, max_items=count)

        if not results:
            await query.message.reply_text("❌ No content found on this profile.")
            return WAITING_FOR_CONTENT

        await query.message.reply_text(f"📦 Found {len(results)} items. Sending...")

        sent = 0
        for item in results:
            try:
                with open(item['path'], 'rb') as f:
                    if item['type'] == 'image':
                        await query.message.reply_photo(photo=f)
                    else:
                        await query.message.reply_video(video=f, supports_streaming=True)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send item: {e}")

        await query.message.reply_text(f"✅ Sent {sent}/{len(results)} items.")
        context.user_data.clear()
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Profile scrape failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Scraping failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def handle_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, result: dict) -> int:
    """Handle gallery downloads (multiple files)."""
    files = result.get('files', [])
    msg = update.message

    await msg.reply_text(f"📦 Gallery: {len(files)} files found. Sending...")

    sent = 0
    for path in files:
        try:
            ext = os.path.splitext(path)[1].lower()
            with open(path, 'rb') as f:
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    await msg.reply_photo(photo=f)
                else:
                    await msg.reply_video(video=f, supports_streaming=True)
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send gallery item: {e}")

    await msg.reply_text(f"✅ Sent {sent}/{len(files)} items.\n\nSend another link or file!")
    return WAITING_FOR_CONTENT


async def edit_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the legacy edit yes/no prompt (kept for backward compatibility)."""
    query = update.callback_query
    await query.answer()

    if query.data == "action_edit":
        await query.edit_message_text("Let's edit your media!")
        return await show_crop_options(update, context)
    elif query.data == "action_skip":
        input_path = context.user_data.get('input_path')
        content_type = context.user_data.get('content_type', 'video')
        if input_path and os.path.exists(input_path):
            with open(input_path, 'rb') as f:
                if content_type == 'image':
                    await query.message.reply_photo(photo=f, caption="Here's your media.")
                else:
                    await query.message.reply_video(video=f, caption="Here's your media.", supports_streaming=True)
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
    return await create_menu(update, context)


async def ranking_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await ranking_menu(update, context)


async def templates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await template_menu(update, context)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await show_settings_menu(update, context)


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


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Clean up any temp files
    input_path = context.user_data.get('input_path')
    if input_path and os.path.exists(input_path):
        try:
            os.remove(input_path)
        except OSError:
            pass
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Send new content to start.")
    return WAITING_FOR_CONTENT


# ── Main ────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", menu_command),
            CommandHandler("create", create_command),
            CommandHandler("ranking", ranking_command),
            CommandHandler("templates", templates_command),
            CommandHandler("presets", manage_presets),
            CommandHandler("settings", settings_command),
            MessageHandler(
                filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                handle_content
            ),
        ],
        states={
            # Content input
            WAITING_FOR_CONTENT: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    handle_content
                ),
            ],

            # ── New download action flow ──
            DOWNLOAD_ACTIONS: [
                CallbackQueryHandler(download_action_handler, pattern="^dl_"),
            ],

            # ── Overlay flow ──
            OVERLAY_MENU: [
                CallbackQueryHandler(overlay_menu_handler, pattern="^ov_"),
            ],
            BORDER_COLOR: [
                CallbackQueryHandler(border_color_handler, pattern="^brd_"),
            ],
            BORDER_CUSTOM_HEX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, border_custom_hex_handler),
            ],
            CAPTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, caption_text_handler),
            ],
            CAPTION_POSITION: [
                CallbackQueryHandler(caption_position_handler, pattern="^cpos_"),
            ],
            CAPTION_STYLE: [
                CallbackQueryHandler(caption_style_handler, pattern="^cstyle_"),
            ],
            SLUDGE_CATEGORY: [
                CallbackQueryHandler(sludge_category_handler, pattern="^sludge_"),
            ],
            SLUDGE_LAYOUT: [
                CallbackQueryHandler(sludge_layout_handler, pattern="^slayout_"),
            ],
            ASPECT_CONVERT: [
                CallbackQueryHandler(aspect_convert_handler, pattern="^ar_"),
            ],
            ASPECT_METHOD: [
                CallbackQueryHandler(aspect_method_handler, pattern="^arm_"),
            ],

            # ── Template flow ──
            TEMPLATE_CHOICE: [
                CallbackQueryHandler(template_choice_handler, pattern="^tpl_"),
            ],

            # ── AI features ──
            AUTO_CAPTION_STYLE: [
                CallbackQueryHandler(auto_caption_handler, pattern="^cap_"),
            ],
            VOICEOVER_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, voiceover_text_handler),
            ],
            VOICEOVER_VOICE: [
                CallbackQueryHandler(voiceover_voice_handler, pattern="^voice_"),
            ],
            VOICEOVER_MODE: [
                CallbackQueryHandler(voiceover_mode_handler, pattern="^vom_"),
            ],

            # ── Effects ──
            SPEED_SELECT: [
                CallbackQueryHandler(speed_handler, pattern="^spd_"),
            ],
            VOICE_EFFECT_SELECT: [
                CallbackQueryHandler(voice_effect_handler, pattern="^vfx_"),
            ],
            MUSIC_CATEGORY: [
                CallbackQueryHandler(music_handler, pattern="^mus_"),
            ],

            # ── Full process ──
            FULL_PROCESS_CONFIRM: [
                CallbackQueryHandler(full_process_handler, pattern="^full_"),
            ],

            # ── Slideshow ──
            SLIDESHOW_IMAGES: [
                MessageHandler(filters.PHOTO, slideshow_handler),
                CallbackQueryHandler(slideshow_handler, pattern="^slideshow_"),
            ],

            # ── Profile scraping ──
            PROFILE_SCRAPE: [
                CallbackQueryHandler(profile_scrape_handler, pattern="^scrape_"),
            ],

            # ── Text input actions ──
            TEXT_INPUT_ACTION: [
                CallbackQueryHandler(text_input_action_handler, pattern="^txt_"),
            ],

            # ── Tweet pipeline ──
            PAGE_SELECT: [
                CallbackQueryHandler(page_select_handler, pattern="^tw_page_"),
            ],
            TWEET_RATIO: [
                CallbackQueryHandler(tweet_ratio_handler, pattern="^tw_ratio_"),
            ],
            TWEET_BG_COLOR: [
                CallbackQueryHandler(tweet_bg_handler, pattern="^tw_bg_"),
            ],
            TWEET_XLOGO: [
                CallbackQueryHandler(tweet_xlogo_handler, pattern="^tw_xlogo_"),
            ],

            # ── Settings ──
            SETTINGS_MENU: [
                CallbackQueryHandler(settings_handler, pattern="^set_"),
            ],

            # ── Legacy edit prompt ──
            EDIT_PROMPT: [
                CallbackQueryHandler(edit_prompt_handler, pattern="^action_"),
            ],
            ACTION_CHOICE: [
                CallbackQueryHandler(action_choice_handler, pattern="^action_"),
            ],

            # ── Existing editing flow ──
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

            # ── Preset management ──
            MANAGE_PRESETS: [
                CallbackQueryHandler(preset_action),
            ],
            CREATE_PRESET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_preset),
            ],

            # ── Video creation flow ──
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

            # ── Template management ──
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

            # ── Ranking video flow ──
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
            CommandHandler("menu", menu_command),
            CommandHandler("create", create_command),
            CommandHandler("ranking", ranking_command),
            CommandHandler("templates", templates_command),
            CommandHandler("presets", manage_presets),
            CommandHandler("settings", settings_command),
        ],
    )

    app.add_handler(conv)

    print("Content Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
