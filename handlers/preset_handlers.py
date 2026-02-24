"""Handlers for filter preset management."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import PRESETS_FILE, WAITING_FOR_CONTENT, MANAGE_PRESETS, CREATE_PRESET
from core.presets import PresetManager

logger = logging.getLogger(__name__)


async def manage_presets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    preset_manager = PresetManager(PRESETS_FILE)
    presets = preset_manager.list_presets()
    preset_list = "\n".join([f"- *{p['name']}*: {p['description']}" for p in presets.values()])
    keyboard = [
        [InlineKeyboardButton("Create Preset", callback_data="preset_create")],
        [InlineKeyboardButton("Delete Preset", callback_data="preset_delete")],
        [InlineKeyboardButton("Back", callback_data="preset_back")],
    ]
    await update.message.reply_text(
        f"*Filter Presets*\n\n{preset_list}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return MANAGE_PRESETS


async def preset_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    preset_manager = PresetManager(PRESETS_FILE)

    if query.data == "preset_back":
        await query.edit_message_text("Send a link or file to process!")
        return WAITING_FOR_CONTENT
    elif query.data == "preset_create":
        await query.edit_message_text(
            "*Create Preset*\n\nSend in format:\n\n"
            "`name: My Filter`\n"
            "`description: Cool look`\n"
            "`saturation: 1.2`\n"
            "`contrast: 1.1`\n"
            "`brightness: 1.0`\n"
            "`temperature: 20`\n\n"
            "_Values are multipliers (1.0 = normal)_",
            parse_mode='Markdown'
        )
        return CREATE_PRESET
    elif query.data == "preset_delete":
        custom = {
            k: v for k, v in preset_manager.list_presets().items()
            if k not in PresetManager.DEFAULT_PRESETS
        }
        if not custom:
            await query.edit_message_text("No custom presets to delete.")
            return WAITING_FOR_CONTENT
        keyboard = [
            [InlineKeyboardButton(f"Delete {p['name']}", callback_data=f"delete_{k}")]
            for k, p in custom.items()
        ]
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="preset_back")])
        await query.edit_message_text(
            "Select preset to delete:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MANAGE_PRESETS
    elif query.data.startswith("delete_"):
        key = query.data.replace("delete_", "")
        preset_manager.delete_preset(key)
        await query.edit_message_text("Deleted!")
        return WAITING_FOR_CONTENT
    return MANAGE_PRESETS


async def create_preset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    preset_manager = PresetManager(PRESETS_FILE)
    try:
        lines = update.message.text.strip().split('\n')
        config = {}
        for line in lines:
            if ':' in line:
                k, v = line.split(':', 1)
                config[k.strip().lower()] = v.strip()
        name = config.get('name', 'Custom')
        desc = config.get('description', 'Custom filter')
        filters = {}
        for k in ['saturation', 'contrast', 'brightness']:
            if k in config:
                filters[k] = float(config[k])
        if 'temperature' in config:
            filters['temperature'] = int(config['temperature'])
        key = ''.join(c for c in name.lower().replace(' ', '_') if c.isalnum() or c == '_')
        preset_manager.add_preset(key, name, desc, filters)
        await update.message.reply_text(
            f"Created '*{name}*'!\n\nSend content to try it.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
    return WAITING_FOR_CONTENT
