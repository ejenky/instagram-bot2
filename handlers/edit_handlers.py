"""Handlers for the video/image editing flow."""

import os
import tempfile
import subprocess
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    REEL_WIDTH, REEL_HEIGHT, DEFAULT_WATERMARK_TEXT, WATERMARK_IMAGE_PATH,
    DATA_DIR, DIMENSION_PRESETS,
    WAITING_FOR_CONTENT, CHOOSE_CROP, CHOOSE_DIMENSIONS, CHOOSE_MODE,
    ENTER_TEXT, CONFIRM_TEXT, CHOOSE_WATERMARK, ENTER_WATERMARK_TEXT,
    CHOOSE_FILTER,
)
from core.presets import PresetManager
from editors.video_editor import VideoEditor
from editors.image_editor import ImageEditor

logger = logging.getLogger(__name__)


async def show_crop_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("Smart Crop", callback_data="crop_smart"),
            InlineKeyboardButton("Center", callback_data="crop_center"),
        ],
        [
            InlineKeyboardButton("Top", callback_data="crop_top"),
            InlineKeyboardButton("Bottom", callback_data="crop_bottom"),
        ],
        [InlineKeyboardButton("Fit (Bars)", callback_data="crop_fit")],
    ]
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "*How to crop?*\n\n"
        "- *Smart*: Auto-detect and remove text overlays\n"
        "- *Center*: Fill frame, centered\n"
        "- *Top/Bottom*: Keep top or bottom\n"
        "- *Fit*: Show all content with bars",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CHOOSE_CROP


async def crop_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['crop_mode'] = query.data.replace("crop_", "")
    return await show_dimensions_options(update, context)


async def show_dimensions_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = []
    row = []
    for key, preset in DIMENSION_PRESETS.items():
        row.append(InlineKeyboardButton(preset['label'], callback_data=f"dim_{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    query = update.callback_query
    if query:
        await query.edit_message_text(
            f"Crop: *{context.user_data['crop_mode'].title()}*\n\n"
            "Select output dimensions:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        msg = update.message or update.callback_query.message
        await msg.reply_text(
            "Select output dimensions:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    return CHOOSE_DIMENSIONS


async def dimensions_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    dim_key = query.data.replace("dim_", "")
    preset = DIMENSION_PRESETS.get(dim_key)
    if preset:
        context.user_data['target_width'] = preset['width']
        context.user_data['target_height'] = preset['height']
        context.user_data['dimension_label'] = preset['label']
    else:
        context.user_data['target_width'] = REEL_WIDTH
        context.user_data['target_height'] = REEL_HEIGHT
        context.user_data['dimension_label'] = '9:16 (Reels)'

    # Ask dark/light mode
    keyboard = [
        [InlineKeyboardButton("Dark Mode", callback_data="mode_dark")],
        [InlineKeyboardButton("Light Mode", callback_data="mode_light")],
    ]
    await query.edit_message_text(
        f"Dimensions: *{context.user_data['dimension_label']}*\n\n"
        "Choose background:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CHOOSE_MODE


async def mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['dark_mode'] = query.data == "mode_dark"
    mode_name = "Dark" if context.user_data['dark_mode'] else "Light"

    keyboard = [
        [
            InlineKeyboardButton("Add Text", callback_data="text_yes"),
            InlineKeyboardButton("Skip", callback_data="text_no"),
        ]
    ]
    await query.edit_message_text(
        f"Mode: *{mode_name}*\n\nAdd text above the content?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ENTER_TEXT


async def text_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "text_yes":
        await query.edit_message_text(
            "Enter the text to appear above:\n\n_Tip: Use short punchy text like the viral pages_",
            parse_mode='Markdown'
        )
        return CONFIRM_TEXT
    context.user_data['top_text'] = None
    return await show_watermark_options(update, context)


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['top_text'] = update.message.text.strip()
    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="text_confirm"),
            InlineKeyboardButton("Re-enter", callback_data="text_reenter"),
        ]
    ]
    await update.message.reply_text(
        f"Preview:\n\n*{context.user_data['top_text']}*\n\nLook good?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CONFIRM_TEXT


async def text_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "text_reenter":
        await query.edit_message_text("Enter the text again:")
        return CONFIRM_TEXT
    return await show_watermark_options(update, context)


async def show_watermark_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton(f"Default ({DEFAULT_WATERMARK_TEXT})", callback_data="wm_default")],
        [
            InlineKeyboardButton("Custom Text", callback_data="wm_custom"),
            InlineKeyboardButton("Image", callback_data="wm_image"),
        ],
        [InlineKeyboardButton("No Watermark", callback_data="wm_none")],
    ]
    query = update.callback_query
    if query:
        await query.edit_message_text(
            "*Watermark:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "*Watermark:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    return CHOOSE_WATERMARK


async def watermark_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "wm_default":
        context.user_data['watermark_text'] = DEFAULT_WATERMARK_TEXT
        context.user_data['watermark_image'] = None
    elif query.data == "wm_custom":
        await query.edit_message_text("Enter watermark text (e.g. @yourusername):")
        return ENTER_WATERMARK_TEXT
    elif query.data == "wm_image":
        if os.path.exists(WATERMARK_IMAGE_PATH):
            context.user_data['watermark_text'] = None
            context.user_data['watermark_image'] = WATERMARK_IMAGE_PATH
        else:
            await query.edit_message_text("No watermark image configured. Set WATERMARK_PATH env var.")
            return await show_watermark_options(update, context)
    else:
        context.user_data['watermark_text'] = None
        context.user_data['watermark_image'] = None
    return await show_filter_options(update, context)


async def receive_watermark_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['watermark_text'] = update.message.text.strip()
    context.user_data['watermark_image'] = None
    return await show_filter_options(update, context)


async def show_filter_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from core.config import PRESETS_FILE
    preset_manager = PresetManager(PRESETS_FILE)
    presets = preset_manager.list_presets()
    keyboard = []
    row = []
    for key, preset in presets.items():
        row.append(InlineKeyboardButton(preset['name'], callback_data=f"filter_{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(
        "*Choose filter:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CHOOSE_FILTER


async def filter_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    from core.config import PRESETS_FILE
    preset_manager = PresetManager(PRESETS_FILE)
    context.user_data['filter_preset'] = query.data.replace("filter_", "")
    preset = preset_manager.get_preset(context.user_data['filter_preset'])
    await query.edit_message_text(
        f"Filter: *{preset['name'] if preset else 'None'}*",
        parse_mode='Markdown'
    )
    return await process_content(update, context)


async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute the full editing pipeline."""
    msg = update.callback_query.message if update.callback_query else update.message
    status = await msg.reply_text("Processing...")
    try:
        from core.config import PRESETS_FILE
        preset_manager = PresetManager(PRESETS_FILE)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = context.user_data['input_path']
            content_type = context.user_data['content_type']
            dark_mode = context.user_data.get('dark_mode', True)
            target_w = context.user_data.get('target_width', REEL_WIDTH)
            target_h = context.user_data.get('target_height', REEL_HEIGHT)

            rand = ''.join(__import__('random').choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
            ext = 'mp4' if content_type == 'video' else 'jpg'
            output_path = os.path.join(temp_dir, f'output_{rand}.{ext}')

            if content_type == 'video':
                await status.edit_text("Processing video...\nApplying edits...")
                editor = VideoEditor(temp_dir, preset_manager)
                await editor.process(
                    input_path, output_path,
                    crop_mode=context.user_data.get('crop_mode', 'smart'),
                    top_text=context.user_data.get('top_text'),
                    watermark_text=context.user_data.get('watermark_text'),
                    watermark_image=context.user_data.get('watermark_image'),
                    dark_mode=dark_mode,
                    filter_preset=context.user_data.get('filter_preset'),
                    target_width=target_w,
                    target_height=target_h,
                )
                await status.edit_text("Uploading...")
                with open(output_path, 'rb') as f:
                    await msg.reply_video(
                        video=f,
                        caption="Done! Ready for posting. Fresh metadata applied.",
                        supports_streaming=True
                    )
            else:
                await status.edit_text("Processing image...\nApplying edits...")
                editor = ImageEditor(temp_dir, preset_manager)
                await editor.process(
                    input_path, output_path,
                    crop_mode=context.user_data.get('crop_mode', 'smart'),
                    top_text=context.user_data.get('top_text'),
                    watermark_text=context.user_data.get('watermark_text'),
                    watermark_image=context.user_data.get('watermark_image'),
                    filter_preset=context.user_data.get('filter_preset'),
                    dark_mode=dark_mode,
                    target_width=target_w,
                    target_height=target_h,
                )
                await status.edit_text("Uploading...")
                with open(output_path, 'rb') as f:
                    await msg.reply_photo(
                        photo=f,
                        caption="Done! Ready for Instagram. Fresh metadata applied."
                    )

        await status.delete()
        if os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await msg.reply_text("Send another link or file, or use /create to make a video from scratch!")
        return WAITING_FOR_CONTENT
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        await status.edit_text(f"Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT
