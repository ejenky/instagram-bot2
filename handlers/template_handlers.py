"""Handlers for template management."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    TEMPLATES_FILE, WAITING_FOR_CONTENT,
    TEMPLATE_MENU, TEMPLATE_NAME, TEMPLATE_DESCRIBE, TEMPLATE_SELECT,
    CREATE_MENU,
)
from core.template_manager import TemplateManager

logger = logging.getLogger(__name__)


def _get_template_manager():
    return TemplateManager(TEMPLATES_FILE)


async def template_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show template management menu."""
    tm = _get_template_manager()
    templates = tm.list_templates()

    keyboard = [
        [InlineKeyboardButton("Create from Description", callback_data="tpl_from_desc")],
    ]

    if templates:
        for key, tpl in templates.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{tpl['name']}",
                    callback_data=f"tpl_use_{key}"
                ),
                InlineKeyboardButton("Delete", callback_data=f"tpl_del_{key}"),
            ])

    keyboard.append([InlineKeyboardButton("Back", callback_data="tpl_back")])

    text = "*Templates*\n\n"
    if templates:
        for key, tpl in templates.items():
            text += f"- *{tpl['name']}*: {tpl['description']}\n"
    else:
        text += "No templates saved yet.\n"
    text += "\nCreate templates to save video configurations for reuse."

    query = update.callback_query
    if query:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        msg = update.message or query.message
        await msg.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    return TEMPLATE_MENU


async def template_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle template naming."""
    query = update.callback_query
    msg = update.message

    if query:
        await query.answer()
        action = query.data

        if action == "tpl_from_desc":
            await query.edit_message_text(
                "Enter a name for your new template:"
            )
            context.user_data['template_source'] = 'description'
            return TEMPLATE_NAME

        elif action.startswith("tpl_use_"):
            key = action.replace("tpl_use_", "")
            tm = _get_template_manager()
            tpl = tm.get_template(key)
            if tpl:
                config = tpl.get('config', {})
                # Apply template config to user_data
                context.user_data.update({
                    'template_applied': key,
                    'crop_mode': config.get('crop_mode', 'smart'),
                    'dark_mode': config.get('dark_mode', True),
                })
                dims = config.get('dimensions', {})
                if dims:
                    context.user_data['target_width'] = dims.get('width', 1080)
                    context.user_data['target_height'] = dims.get('height', 1920)

                await query.edit_message_text(
                    f"Template *{tpl['name']}* applied!\n\n"
                    f"Config: {tpl['description']}\n\n"
                    "Send content to edit with this template, or use /create to build a new video.",
                    parse_mode='Markdown'
                )
                return WAITING_FOR_CONTENT

        elif action.startswith("tpl_del_"):
            key = action.replace("tpl_del_", "")
            tm = _get_template_manager()
            if tm.delete_template(key):
                await query.edit_message_text("Template deleted.")
            else:
                await query.edit_message_text("Template not found.")
            return await template_menu(update, context)

        elif action == "tpl_back":
            # Check where we came from
            if 'creator' in context.user_data:
                from handlers.create_handlers import create_menu
                return await create_menu(update, context)
            await query.edit_message_text("Send a link or file to start!")
            return WAITING_FOR_CONTENT

    elif msg:
        name = msg.text.strip()
        context.user_data['template_name'] = name

        source = context.user_data.get('template_source', 'description')
        if source == 'creator':
            # Save current creator config as template
            creator = context.user_data.get('creator')
            if creator:
                tm = _get_template_manager()
                config = creator.get_config()
                # Remove file paths from config (not portable)
                config.pop('background_audio', None)
                config.pop('narration_audio', None)
                for clip in config.get('clips', []):
                    clip.pop('source_path', None)
                key = tm.create_template(name, f"Created from video creator", config)
                await msg.reply_text(
                    f"Template *{name}* saved!\n"
                    "You can load it from /templates.",
                    parse_mode='Markdown'
                )
                from handlers.create_handlers import create_menu
                return await create_menu(update, context)
        else:
            await msg.reply_text(
                "Now describe this template.\n"
                "What kind of video should it create?\n\n"
                "Example: \"Dark mode 9:16 reel with white bold text at top, "
                "@username watermark, high contrast filter\""
            )
            return TEMPLATE_DESCRIBE

    return TEMPLATE_NAME


async def template_describe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle template description input."""
    msg = update.message
    if not msg:
        return TEMPLATE_DESCRIBE

    description = msg.text.strip()
    name = context.user_data.get('template_name', 'Untitled')

    tm = _get_template_manager()
    key = tm.create_from_description(name, description)

    await msg.reply_text(
        f"Template *{name}* created!\n\n"
        f"Description: {description}\n\n"
        "Use /templates to view and apply your templates.",
        parse_mode='Markdown'
    )
    return WAITING_FOR_CONTENT


async def template_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle template selection for applying."""
    return await template_menu(update, context)
