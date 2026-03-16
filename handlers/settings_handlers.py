"""Handlers for user settings/defaults."""

import os
import json
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    SETTINGS_MENU, WAITING_FOR_CONTENT, SETTINGS_FILE, DATA_DIR,
)

logger = logging.getLogger(__name__)


def _load_settings() -> dict:
    """Load user settings from file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        'default_template': 'reel',
        'default_caption_style': 'bold_pop',
        'default_voice': 'deep_male',
        'auto_randomize': True,
        'auto_captions': False,
    }


def _save_settings(settings: dict):
    """Save user settings to file."""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show settings menu with current values."""
    settings = _load_settings()

    template_names = {
        'reel': 'Reel 9:16', 'story': 'Story 9:16',
        'square': 'Square 1:1', 'landscape': 'Landscape 16:9',
    }
    caption_names = {
        'standard': 'Standard', 'word_by_word': 'Word-by-word',
        'bold_pop': 'Bold Pop', 'color_wave': 'Color Wave',
    }
    voice_names = {
        'deep_male': 'Deep Male', 'female': 'Female',
        'dramatic': 'Dramatic', 'whisper': 'Whisper',
    }

    text = (
        "⚙️ *Settings*\n\n"
        f"Default template: *{template_names.get(settings['default_template'], settings['default_template'])}*\n"
        f"Default caption style: *{caption_names.get(settings['default_caption_style'], settings['default_caption_style'])}*\n"
        f"Default voice: *{voice_names.get(settings['default_voice'], settings['default_voice'])}*\n"
        f"Auto-randomize: *{'ON' if settings['auto_randomize'] else 'OFF'}*\n"
        f"Auto-captions: *{'ON' if settings['auto_captions'] else 'OFF'}*"
    )

    keyboard = [
        [InlineKeyboardButton(
            f"Template: {template_names.get(settings['default_template'], '?')}",
            callback_data="set_template"
        )],
        [InlineKeyboardButton(
            f"Caption: {caption_names.get(settings['default_caption_style'], '?')}",
            callback_data="set_caption"
        )],
        [InlineKeyboardButton(
            f"Voice: {voice_names.get(settings['default_voice'], '?')}",
            callback_data="set_voice"
        )],
        [InlineKeyboardButton(
            f"Auto-randomize: {'ON' if settings['auto_randomize'] else 'OFF'}",
            callback_data="set_randomize"
        )],
        [InlineKeyboardButton(
            f"Auto-captions: {'ON' if settings['auto_captions'] else 'OFF'}",
            callback_data="set_autocaptions"
        )],
        [InlineKeyboardButton("✅ Done", callback_data="set_done")],
    ]

    msg = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    else:
        await msg.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    return SETTINGS_MENU


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle settings menu interactions."""
    query = update.callback_query
    await query.answer()
    settings = _load_settings()

    if query.data == 'set_done':
        await query.edit_message_text("Settings saved! Send a link or file to start.")
        return WAITING_FOR_CONTENT

    elif query.data == 'set_template':
        templates = ['reel', 'story', 'square', 'landscape']
        current = settings.get('default_template', 'reel')
        idx = templates.index(current) if current in templates else 0
        settings['default_template'] = templates[(idx + 1) % len(templates)]

    elif query.data == 'set_caption':
        styles = ['standard', 'word_by_word', 'bold_pop', 'color_wave']
        current = settings.get('default_caption_style', 'bold_pop')
        idx = styles.index(current) if current in styles else 0
        settings['default_caption_style'] = styles[(idx + 1) % len(styles)]

    elif query.data == 'set_voice':
        voices = ['deep_male', 'female', 'dramatic', 'whisper']
        current = settings.get('default_voice', 'deep_male')
        idx = voices.index(current) if current in voices else 0
        settings['default_voice'] = voices[(idx + 1) % len(voices)]

    elif query.data == 'set_randomize':
        settings['auto_randomize'] = not settings.get('auto_randomize', True)

    elif query.data == 'set_autocaptions':
        settings['auto_captions'] = not settings.get('auto_captions', False)

    _save_settings(settings)
    return await show_settings_menu(update, context)
