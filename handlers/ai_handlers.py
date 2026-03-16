"""Handlers for AI-powered features - voiceover, auto-description."""

import os
import tempfile
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    WAITING_FOR_CONTENT, VOICEOVER_TEXT, VOICEOVER_VOICE, VOICEOVER_MODE,
    TEXT_INPUT_ACTION,
)
from core.ai import VOICES

logger = logging.getLogger(__name__)


async def voiceover_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle voiceover script text input."""
    context.user_data['voiceover_text'] = update.message.text.strip()

    keyboard = []
    for key, voice in VOICES.items():
        keyboard.append([InlineKeyboardButton(voice['name'], callback_data=f"voice_{key}")])

    await update.message.reply_text(
        "🎤 *Pick a voice:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return VOICEOVER_VOICE


async def voiceover_voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle voice selection."""
    query = update.callback_query
    await query.answer()

    context.user_data['voiceover_voice'] = query.data.replace('voice_', '')

    # Check if we have a video to overlay on
    if context.user_data.get('input_path'):
        keyboard = [
            [InlineKeyboardButton("🔇 Replace Audio", callback_data="vom_replace")],
            [InlineKeyboardButton("🔊 Mix with Original", callback_data="vom_mix")],
        ]
        await query.edit_message_text(
            "How should the voiceover be added?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return VOICEOVER_MODE
    else:
        # No video, just generate the audio
        return await _generate_voiceover_only(update, context)


async def voiceover_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle voiceover mode (replace/mix) and execute."""
    query = update.callback_query
    await query.answer()

    mode = query.data.replace('vom_', '')
    text = context.user_data.get('voiceover_text', '')
    voice_key = context.user_data.get('voiceover_voice', 'deep_male')
    input_path = context.user_data.get('input_path')

    await query.edit_message_text("⏳ Generating voiceover...")

    try:
        from core.ai import text_to_speech
        from editors.effects import overlay_voiceover
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate TTS audio
            audio_path = os.path.join(temp_dir, 'voiceover.mp3')
            await text_to_speech(text, voice_key, audio_path)

            # Overlay on video
            await query.message.edit_text("⏳ Overlaying voiceover...")
            with_vo = os.path.join(temp_dir, 'with_vo.mp4')
            await overlay_voiceover(input_path, audio_path, with_vo, mode)

            # Randomize
            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(with_vo, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"🎤 Voiceover added ({mode}) + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Voiceover failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Voiceover failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def _generate_voiceover_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generate voiceover audio without video overlay (for text-only input)."""
    query = update.callback_query
    text = context.user_data.get('voiceover_text', '')
    voice_key = context.user_data.get('voiceover_voice', 'deep_male')

    await query.edit_message_text("⏳ Generating voiceover...")

    try:
        from core.ai import text_to_speech

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = os.path.join(temp_dir, 'voiceover.mp3')
            await text_to_speech(text, voice_key, audio_path)

            with open(audio_path, 'rb') as f:
                await query.message.reply_audio(
                    audio=f,
                    caption="🎤 Generated voiceover audio.",
                    title="Voiceover"
                )

        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"TTS failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ TTS failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle plain text input (not a URL) - offer text-related actions."""
    text = update.message.text.strip()
    context.user_data['input_text'] = text

    keyboard = [
        [InlineKeyboardButton("🎤 Generate Voiceover", callback_data="txt_voiceover")],
        [InlineKeyboardButton("📝 Use as Caption", callback_data="txt_caption")],
    ]
    await update.message.reply_text(
        "What would you like to do with this text?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TEXT_INPUT_ACTION


async def text_input_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input action selection."""
    query = update.callback_query
    await query.answer()

    if query.data == 'txt_voiceover':
        context.user_data['voiceover_text'] = context.user_data.get('input_text', '')
        keyboard = []
        for key, voice in VOICES.items():
            keyboard.append([InlineKeyboardButton(voice['name'], callback_data=f"voice_{key}")])

        await query.edit_message_text(
            "🎤 *Pick a voice:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return VOICEOVER_VOICE

    elif query.data == 'txt_caption':
        context.user_data['saved_caption'] = context.user_data.get('input_text', '')
        await query.edit_message_text(
            f"📝 Caption saved: *{context.user_data['saved_caption']}*\n\n"
            "Send a video or link to apply this caption to.",
            parse_mode='Markdown'
        )
        return WAITING_FOR_CONTENT

    return TEXT_INPUT_ACTION
