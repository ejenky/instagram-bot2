"""Handlers for the download flow - action menu after downloading media."""

import os
import shutil
import tempfile
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    WAITING_FOR_CONTENT, DOWNLOAD_ACTIONS, OVERLAY_MENU,
    TEMPLATE_CHOICE, AUTO_CAPTION_STYLE, VOICEOVER_TEXT,
    FULL_PROCESS_CONFIRM, SPEED_SELECT, VOICE_EFFECT_SELECT,
    MUSIC_CATEGORY, ASPECT_CONVERT, CHOOSE_CROP, PROFILE_SCRAPE,
    BATCH_PROCESSING, TEXT_INPUT_ACTION, SLIDESHOW_IMAGES,
)
from core.randomizer import quick_randomize
from core.media_info import get_media_info

logger = logging.getLogger(__name__)


async def show_download_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show the action menu after downloading/receiving media."""
    content_type = context.user_data.get('content_type', 'video')
    msg = update.message or update.callback_query.message

    if content_type == 'image':
        keyboard = [
            [InlineKeyboardButton("📥 Download Clean", callback_data="dl_quick")],
            [InlineKeyboardButton("🖼️ Add Text", callback_data="dl_overlay")],
            [InlineKeyboardButton("🎬 Make Slideshow", callback_data="dl_slideshow")],
            [InlineKeyboardButton("✏️ Full Edit", callback_data="dl_edit")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📥 Quick Download", callback_data="dl_quick")],
            [
                InlineKeyboardButton("🖼️ Add Overlay", callback_data="dl_overlay"),
                InlineKeyboardButton("🎬 Use Template", callback_data="dl_template"),
            ],
            [
                InlineKeyboardButton("🎤 Add Voiceover", callback_data="dl_voiceover"),
                InlineKeyboardButton("📝 Auto Captions", callback_data="dl_captions"),
            ],
            [
                InlineKeyboardButton("⚡ Full Process", callback_data="dl_full"),
                InlineKeyboardButton("✏️ Full Edit", callback_data="dl_edit"),
            ],
            [
                InlineKeyboardButton("🔄 Change Speed", callback_data="dl_speed"),
                InlineKeyboardButton("🎵 Add Music", callback_data="dl_music"),
            ],
            [InlineKeyboardButton("🎭 Voice Effect", callback_data="dl_voice_fx")],
        ]

    await msg.reply_text(
        "What would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return DOWNLOAD_ACTIONS


async def download_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle action selection after download."""
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == 'dl_quick':
        return await quick_download(update, context)
    elif action == 'dl_overlay':
        return await show_overlay_menu(update, context)
    elif action == 'dl_template':
        return await show_template_menu(update, context)
    elif action == 'dl_voiceover':
        await query.edit_message_text(
            "🎤 *Voiceover*\n\nType your voiceover script:",
            parse_mode='Markdown'
        )
        return VOICEOVER_TEXT
    elif action == 'dl_captions':
        return await show_caption_styles(update, context)
    elif action == 'dl_full':
        return await show_full_process_confirm(update, context)
    elif action == 'dl_edit':
        await query.edit_message_text("Let's edit your media!")
        from handlers.edit_handlers import show_crop_options
        return await show_crop_options(update, context)
    elif action == 'dl_speed':
        return await show_speed_options(update, context)
    elif action == 'dl_music':
        return await show_music_options(update, context)
    elif action == 'dl_voice_fx':
        return await show_voice_effect_options(update, context)
    elif action == 'dl_slideshow':
        context.user_data['slideshow_images'] = [context.user_data.get('input_path')]
        await query.edit_message_text(
            "🎬 *Slideshow Creator*\n\n"
            "Send more images to add to the slideshow.\n"
            "When done, press the button below.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Create Slideshow", callback_data="slideshow_create")]
            ])
        )
        return SLIDESHOW_IMAGES

    return DOWNLOAD_ACTIONS


async def quick_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Quick download with metadata randomization only."""
    query = update.callback_query
    msg = query.message

    await query.edit_message_text("⏳ Randomizing metadata...")

    input_path = context.user_data.get('input_path')
    content_type = context.user_data.get('content_type', 'video')
    is_video = content_type == 'video'

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            ext = 'mp4' if is_video else 'jpg'
            output_path = os.path.join(temp_dir, f'output.{ext}')

            await quick_randomize(input_path, output_path, is_video=is_video)

            # Check file size
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            if file_size_mb > 50:
                await msg.reply_text("⚠️ File exceeds 50MB Telegram limit. Compressing...")
                compressed = os.path.join(temp_dir, f'compressed.{ext}')
                await _compress_file(output_path, compressed, is_video)
                output_path = compressed

            with open(output_path, 'rb') as f:
                if is_video:
                    await msg.reply_video(
                        video=f,
                        caption="📥 Downloaded & randomized. Fresh metadata applied.",
                        supports_streaming=True
                    )
                else:
                    await msg.reply_photo(
                        photo=f,
                        caption="📥 Downloaded & randomized. EXIF stripped."
                    )

        # Cleanup
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await msg.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Quick download failed: {e}", exc_info=True)
        await msg.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def show_overlay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show overlay type selection."""
    from handlers.overlay_handlers import show_overlay_options
    return await show_overlay_options(update, context)


async def show_template_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show template format selection."""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📱 Reel / Short (9:16)", callback_data="tpl_reel")],
        [InlineKeyboardButton("📸 Story (9:16, 15s max)", callback_data="tpl_story")],
        [InlineKeyboardButton("⬜ Feed Post (1:1)", callback_data="tpl_square")],
        [InlineKeyboardButton("🖥️ Landscape (16:9)", callback_data="tpl_landscape")],
        [InlineKeyboardButton("🔙 Back", callback_data="tpl_back")],
    ]
    await query.edit_message_text(
        "🎬 *Choose a template:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return TEMPLATE_CHOICE


async def template_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle template format selection."""
    query = update.callback_query
    await query.answer()

    if query.data == 'tpl_back':
        return await show_download_actions(update, context)

    template_map = {
        'tpl_reel': 'reel',
        'tpl_story': 'story',
        'tpl_square': 'square',
        'tpl_landscape': 'landscape',
    }
    template = template_map.get(query.data)
    if not template:
        return TEMPLATE_CHOICE

    await query.edit_message_text(f"⏳ Applying {template} template...")

    input_path = context.user_data.get('input_path')
    try:
        from editors.effects import apply_template_format
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, 'output.mp4')
            await apply_template_format(input_path, output_path, template)

            # Randomize metadata
            from core.randomizer import randomize_video
            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(output_path, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"🎬 {template.title()} template applied + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Template failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Template failed: {e}")
        return await show_download_actions(update, context)


async def show_caption_styles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show auto-caption style selection."""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📺 Standard", callback_data="cap_standard")],
        [InlineKeyboardButton("🎤 Word-by-word", callback_data="cap_word_by_word")],
        [InlineKeyboardButton("💥 Bold Pop", callback_data="cap_bold_pop")],
        [InlineKeyboardButton("🌈 Color Wave", callback_data="cap_color_wave")],
        [InlineKeyboardButton("🔙 Back", callback_data="cap_back")],
    ]
    await query.edit_message_text(
        "📝 *Auto Captions*\n\nChoose caption style:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return AUTO_CAPTION_STYLE


async def auto_caption_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle auto-caption generation and burning."""
    query = update.callback_query
    await query.answer()

    if query.data == 'cap_back':
        return await show_download_actions(update, context)

    style = query.data.replace('cap_', '')
    await query.edit_message_text("⏳ Extracting audio & transcribing...")

    input_path = context.user_data.get('input_path')
    try:
        from core.ai import extract_audio, transcribe_audio, generate_caption
        from editors.effects import burn_subtitles
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract audio
            audio_path = os.path.join(temp_dir, 'audio.wav')
            await extract_audio(input_path, audio_path)

            # Transcribe
            await query.message.edit_text("⏳ Transcribing audio...")
            srt_content = await transcribe_audio(audio_path, response_format='srt')

            srt_path = os.path.join(temp_dir, 'subtitles.srt')
            with open(srt_path, 'w') as f:
                f.write(srt_content)

            # Burn subtitles
            await query.message.edit_text("⏳ Burning captions...")
            captioned = os.path.join(temp_dir, 'captioned.mp4')
            await burn_subtitles(input_path, captioned, srt_path, style)

            # Randomize
            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(captioned, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption="📝 Auto captions applied + randomized.",
                    supports_streaming=True
                )

            # Also generate and send a caption suggestion
            try:
                transcript_text = await transcribe_audio(audio_path, response_format='text')
                caption = await generate_caption(transcript_text)
                await query.message.reply_text(
                    f"💡 *Suggested caption:*\n\n`{caption}`",
                    parse_mode='Markdown'
                )
            except Exception:
                pass  # Caption generation is optional

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Auto captions failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Captions failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def show_full_process_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show full process confirmation."""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("⚡ Go! (Reel format)", callback_data="full_reel")],
        [InlineKeyboardButton("⚡ Go! (Square format)", callback_data="full_square")],
        [InlineKeyboardButton("⚡ Go! (Keep original)", callback_data="full_original")],
        [InlineKeyboardButton("🔙 Back", callback_data="full_back")],
    ]
    await query.edit_message_text(
        "⚡ *Full Process*\n\n"
        "This will:\n"
        "1. Randomize all metadata\n"
        "2. Apply subtle visual changes\n"
        "3. Auto-transcribe & add captions\n"
        "4. Apply template format\n\n"
        "Choose format:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return FULL_PROCESS_CONFIRM


async def full_process_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle full process pipeline."""
    query = update.callback_query
    await query.answer()

    if query.data == 'full_back':
        return await show_download_actions(update, context)

    format_map = {
        'full_reel': 'reel',
        'full_square': 'square',
        'full_original': None,
    }
    template = format_map.get(query.data)
    input_path = context.user_data.get('input_path')

    await query.edit_message_text("⚡ Running full pipeline...")

    try:
        from editors.effects import apply_template_format, burn_subtitles
        from core.ai import extract_audio, transcribe_audio, generate_caption
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            current = input_path

            # Step 1: Apply template if needed
            if template:
                await query.message.edit_text("⚡ [1/3] Applying template...")
                templated = os.path.join(temp_dir, 'templated.mp4')
                await apply_template_format(current, templated, template)
                current = templated

            # Step 2: Try to add captions (non-fatal if fails)
            try:
                await query.message.edit_text("⚡ [2/3] Adding captions...")
                audio_path = os.path.join(temp_dir, 'audio.wav')
                await extract_audio(current, audio_path)
                srt_content = await transcribe_audio(audio_path, response_format='srt')
                srt_path = os.path.join(temp_dir, 'subs.srt')
                with open(srt_path, 'w') as f:
                    f.write(srt_content)
                captioned = os.path.join(temp_dir, 'captioned.mp4')
                await burn_subtitles(current, captioned, srt_path, 'bold_pop')
                current = captioned
            except Exception as e:
                logger.warning(f"Caption step skipped: {e}")

            # Step 3: Randomize
            await query.message.edit_text("⚡ [3/3] Randomizing...")
            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(current, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption="⚡ Full process complete! Ready for posting.",
                    supports_streaming=True
                )

            # Generate caption suggestion
            try:
                audio_path2 = os.path.join(temp_dir, 'audio2.wav')
                await extract_audio(input_path, audio_path2)
                text = await transcribe_audio(audio_path2, response_format='text')
                caption = await generate_caption(text)
                await query.message.reply_text(
                    f"💡 *Suggested caption:*\n\n`{caption}`",
                    parse_mode='Markdown'
                )
            except Exception:
                pass

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Full process failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def show_speed_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show speed selection buttons."""
    query = update.callback_query
    keyboard = [
        [
            InlineKeyboardButton("0.5x Slow-mo", callback_data="spd_0.5"),
            InlineKeyboardButton("0.75x", callback_data="spd_0.75"),
        ],
        [
            InlineKeyboardButton("1.5x", callback_data="spd_1.5"),
            InlineKeyboardButton("2x Fast", callback_data="spd_2.0"),
        ],
        [InlineKeyboardButton("3x Fast", callback_data="spd_3.0")],
        [InlineKeyboardButton("🔙 Back", callback_data="spd_back")],
    ]
    await query.edit_message_text(
        "🔄 *Speed Change*\n\nSelect playback speed:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return SPEED_SELECT


async def speed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle speed change."""
    query = update.callback_query
    await query.answer()

    if query.data == 'spd_back':
        return await show_download_actions(update, context)

    speed = float(query.data.replace('spd_', ''))
    await query.edit_message_text(f"⏳ Changing speed to {speed}x...")

    input_path = context.user_data.get('input_path')
    try:
        from editors.effects import change_speed
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            sped = os.path.join(temp_dir, 'sped.mp4')
            await change_speed(input_path, sped, speed)

            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(sped, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"🔄 Speed: {speed}x + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Speed change failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def show_voice_effect_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show voice effect buttons."""
    from core.config import VOICE_EFFECTS
    query = update.callback_query
    keyboard = []
    for key, fx in VOICE_EFFECTS.items():
        keyboard.append([InlineKeyboardButton(fx['name'], callback_data=f"vfx_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="vfx_back")])
    await query.edit_message_text(
        "🎭 *Voice Effects*\n\nChoose an effect:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return VOICE_EFFECT_SELECT


async def voice_effect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle voice effect application."""
    query = update.callback_query
    await query.answer()

    if query.data == 'vfx_back':
        return await show_download_actions(update, context)

    effect = query.data.replace('vfx_', '')
    await query.edit_message_text(f"⏳ Applying voice effect...")

    input_path = context.user_data.get('input_path')
    try:
        from editors.effects import apply_voice_effect
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            effected = os.path.join(temp_dir, 'effected.mp4')
            await apply_voice_effect(input_path, effected, effect)

            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(effected, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"🎭 Voice effect applied + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Voice effect failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def show_music_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show music category selection."""
    query = update.callback_query
    keyboard = [
        [
            InlineKeyboardButton("🔥 Hype", callback_data="mus_hype"),
            InlineKeyboardButton("😌 Chill", callback_data="mus_chill"),
        ],
        [
            InlineKeyboardButton("🎭 Dramatic", callback_data="mus_dramatic"),
            InlineKeyboardButton("😂 Funny", callback_data="mus_funny"),
        ],
        [InlineKeyboardButton("😢 Sad", callback_data="mus_sad")],
        [InlineKeyboardButton("🎲 Random", callback_data="mus_random")],
        [InlineKeyboardButton("🔙 Back", callback_data="mus_back")],
    ]
    await query.edit_message_text(
        "🎵 *Background Music*\n\nChoose a category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return MUSIC_CATEGORY


async def music_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle background music addition."""
    query = update.callback_query
    await query.answer()

    if query.data == 'mus_back':
        return await show_download_actions(update, context)

    category = query.data.replace('mus_', '')
    if category == 'random':
        category = None

    from editors.effects import list_music_files, add_background_music
    music_files = list_music_files(category)
    if not music_files:
        await query.edit_message_text(
            f"❌ No music files found. Add .mp3 files to {MUSIC_DIR}"
        )
        return await show_download_actions(update, context)

    # Pick a random track from the category
    import random
    track = random.choice(music_files)

    await query.edit_message_text(f"⏳ Adding music: {track['name']}...")

    input_path = context.user_data.get('input_path')
    try:
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            with_music = os.path.join(temp_dir, 'music.mp4')
            await add_background_music(input_path, track['path'], with_music)

            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(with_music, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"🎵 Music added: {track['name']} + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Music failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def slideshow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle slideshow image collection and creation."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == 'slideshow_create':
            images = context.user_data.get('slideshow_images', [])
            if len(images) < 1:
                await query.edit_message_text("Need at least 1 image!")
                return SLIDESHOW_IMAGES

            await query.edit_message_text(f"⏳ Creating slideshow from {len(images)} images...")

            try:
                from editors.effects import create_slideshow
                from core.randomizer import randomize_video

                with tempfile.TemporaryDirectory() as temp_dir:
                    output = os.path.join(temp_dir, 'slideshow.mp4')
                    await create_slideshow(images, output)

                    final_path = os.path.join(temp_dir, 'final.mp4')
                    await randomize_video(output, final_path)

                    with open(final_path, 'rb') as f:
                        await query.message.reply_video(
                            video=f,
                            caption=f"🎬 Slideshow ({len(images)} images) + randomized.",
                            supports_streaming=True
                        )

                context.user_data.clear()
                await query.message.reply_text("Send another link or file!")
                return WAITING_FOR_CONTENT

            except Exception as e:
                logger.error(f"Slideshow failed: {e}", exc_info=True)
                await query.message.reply_text(f"❌ Slideshow failed: {e}")
                context.user_data.clear()
                return WAITING_FOR_CONTENT

    elif update.message and update.message.photo:
        # Add image to slideshow collection
        photo = update.message.photo[-1]
        file = await photo.get_file()
        from core.config import DATA_DIR
        idx = len(context.user_data.get('slideshow_images', []))
        path = os.path.join(DATA_DIR, f'slide_{update.message.from_user.id}_{idx}.jpg')
        await file.download_to_drive(path)
        context.user_data.setdefault('slideshow_images', []).append(path)

        count = len(context.user_data['slideshow_images'])
        await update.message.reply_text(
            f"Added! ({count} images total)\n\nSend more or tap Create.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Create Slideshow", callback_data="slideshow_create")]
            ])
        )
        return SLIDESHOW_IMAGES

    return SLIDESHOW_IMAGES


async def _compress_file(input_path: str, output_path: str, is_video: bool) -> str:
    """Compress file to fit within Telegram's 50MB limit."""
    if is_video:
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-c:v', 'libx264', '-crf', '28', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '96k',
            output_path
        ]
    else:
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-q:v', '8',
            output_path
        ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return output_path


# Needed for _compress_file
import asyncio
