"""Handlers for overlay features - border, text caption, retention/sludge filter."""

import os
import tempfile
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    OVERLAY_MENU, BORDER_COLOR, BORDER_CUSTOM_HEX,
    CAPTION_TEXT, CAPTION_POSITION, CAPTION_STYLE,
    SLUDGE_CATEGORY, SLUDGE_LAYOUT, WAITING_FOR_CONTENT,
    DOWNLOAD_ACTIONS, BORDER_COLORS, TEXT_STYLES, ASPECT_CONVERT, ASPECT_METHOD,
)

logger = logging.getLogger(__name__)


async def show_overlay_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show overlay type selection menu."""
    query = update.callback_query
    content_type = context.user_data.get('content_type', 'video')

    if content_type == 'image':
        keyboard = [
            [InlineKeyboardButton("📝 Add Text", callback_data="ov_caption")],
            [InlineKeyboardButton("🖼️ Add Border", callback_data="ov_border")],
            [InlineKeyboardButton("🔙 Back", callback_data="ov_back")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🖼️ Add Border", callback_data="ov_border")],
            [InlineKeyboardButton("📝 Burn Caption", callback_data="ov_caption")],
            [InlineKeyboardButton("🎮 Retention Filter", callback_data="ov_sludge")],
            [InlineKeyboardButton("📐 Convert Aspect Ratio", callback_data="ov_aspect")],
            [InlineKeyboardButton("🔙 Back", callback_data="ov_back")],
        ]

    await query.edit_message_text(
        "🖼️ *Overlays & Effects*\n\nWhat do you want to add?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return OVERLAY_MENU


async def overlay_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle overlay type selection."""
    query = update.callback_query
    await query.answer()

    if query.data == 'ov_back':
        from handlers.download_handlers import show_download_actions
        return await show_download_actions(update, context)
    elif query.data == 'ov_border':
        return await show_border_colors(update, context)
    elif query.data == 'ov_caption':
        await query.edit_message_text(
            "📝 *Caption Overlay*\n\nType the text you want to burn onto the video:",
            parse_mode='Markdown'
        )
        return CAPTION_TEXT
    elif query.data == 'ov_sludge':
        return await show_sludge_categories(update, context)
    elif query.data == 'ov_aspect':
        return await show_aspect_options(update, context)

    return OVERLAY_MENU


# ── Border ──────────────────────────────────────────────────────────

async def show_border_colors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show border color selection."""
    query = update.callback_query
    keyboard = [
        [
            InlineKeyboardButton("⬛ Black", callback_data="brd_black"),
            InlineKeyboardButton("⬜ White", callback_data="brd_white"),
        ],
        [
            InlineKeyboardButton("🟥 Red", callback_data="brd_red"),
            InlineKeyboardButton("🟦 Blue", callback_data="brd_blue"),
        ],
        [
            InlineKeyboardButton("🟩 Green", callback_data="brd_green"),
            InlineKeyboardButton("🟪 Purple", callback_data="brd_purple"),
        ],
        [
            InlineKeyboardButton("🟧 Orange", callback_data="brd_orange"),
            InlineKeyboardButton("💗 Pink", callback_data="brd_pink"),
        ],
        [InlineKeyboardButton("🎨 Custom Hex", callback_data="brd_custom")],
        [InlineKeyboardButton("🔙 Back", callback_data="brd_back")],
    ]
    await query.edit_message_text(
        "🖼️ *Border Color*\n\nPick a color:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return BORDER_COLOR


async def border_color_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle border color selection."""
    query = update.callback_query
    await query.answer()

    if query.data == 'brd_back':
        return await show_overlay_options(update, context)
    elif query.data == 'brd_custom':
        await query.edit_message_text(
            "Enter a hex color code (e.g. #FF5733):"
        )
        return BORDER_CUSTOM_HEX

    color_key = query.data.replace('brd_', '')
    color_hex = BORDER_COLORS.get(color_key, '#000000')

    return await _apply_border(update, context, color_hex)


async def border_custom_hex_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom hex color input for border."""
    text = update.message.text.strip()
    if not text.startswith('#') or len(text) not in (4, 7):
        await update.message.reply_text("Invalid hex color. Use format #RGB or #RRGGBB:")
        return BORDER_CUSTOM_HEX

    return await _apply_border(update, context, text)


async def _apply_border(update: Update, context: ContextTypes.DEFAULT_TYPE, color: str) -> int:
    """Apply border with given color."""
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(f"⏳ Adding {color} border...")

    input_path = context.user_data.get('input_path')
    try:
        from editors.effects import add_border
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            bordered = os.path.join(temp_dir, 'bordered.mp4')
            await add_border(input_path, bordered, color)

            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(bordered, final_path)

            with open(final_path, 'rb') as f:
                await msg.reply_video(
                    video=f,
                    caption=f"🖼️ Border ({color}) added + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await msg.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Border failed: {e}", exc_info=True)
        await msg.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


# ── Caption Overlay ──────────────────────────────────────────────────

async def caption_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle caption text input."""
    context.user_data['caption_text'] = update.message.text.strip()

    keyboard = [
        [
            InlineKeyboardButton("Top", callback_data="cpos_top"),
            InlineKeyboardButton("Center", callback_data="cpos_center"),
            InlineKeyboardButton("Bottom", callback_data="cpos_bottom"),
        ],
    ]
    await update.message.reply_text(
        "Where should the text go?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CAPTION_POSITION


async def caption_position_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle caption position selection."""
    query = update.callback_query
    await query.answer()
    context.user_data['caption_position'] = query.data.replace('cpos_', '')

    keyboard = []
    for key, style in TEXT_STYLES.items():
        keyboard.append([InlineKeyboardButton(style['name'], callback_data=f"cstyle_{key}")])

    await query.edit_message_text(
        "Text style?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CAPTION_STYLE


async def caption_style_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle caption style selection and apply."""
    query = update.callback_query
    await query.answer()

    style = query.data.replace('cstyle_', '')
    text = context.user_data.get('caption_text', '')
    position = context.user_data.get('caption_position', 'bottom')

    await query.edit_message_text(f"⏳ Burning caption...")

    input_path = context.user_data.get('input_path')
    try:
        from editors.effects import add_text_overlay
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            captioned = os.path.join(temp_dir, 'captioned.mp4')
            await add_text_overlay(input_path, captioned, text, position, style)

            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(captioned, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"📝 Caption added + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Caption failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


# ── Sludge / Retention Filter ──────────────────────────────────────

async def show_sludge_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show retention/sludge clip categories."""
    from core.config import SLUDGE_CATEGORIES
    query = update.callback_query
    keyboard = []
    for key, cat in SLUDGE_CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(cat['name'], callback_data=f"sludge_{key}")])
    keyboard.append([InlineKeyboardButton("🎲 Random", callback_data="sludge_random")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="sludge_back")])

    await query.edit_message_text(
        "🎮 *Retention Filter*\n\nPick a retention clip:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return SLUDGE_CATEGORY


async def sludge_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle sludge category selection."""
    query = update.callback_query
    await query.answer()

    if query.data == 'sludge_back':
        return await show_overlay_options(update, context)

    import random as rand_mod
    if query.data == 'sludge_random':
        from core.config import SLUDGE_CATEGORIES
        context.user_data['sludge_category'] = rand_mod.choice(list(SLUDGE_CATEGORIES.keys()))
    else:
        context.user_data['sludge_category'] = query.data.replace('sludge_', '')

    # Show layout options
    keyboard = [
        [InlineKeyboardButton("⬆️⬇️ Top/Bottom (Reels)", callback_data="slayout_top_bottom")],
        [InlineKeyboardButton("⬅️➡️ Left/Right", callback_data="slayout_left_right")],
        [InlineKeyboardButton("📌 Picture-in-Picture", callback_data="slayout_pip")],
        [InlineKeyboardButton("🔙 Back", callback_data="slayout_back")],
    ]
    await query.edit_message_text(
        "Layout for the retention clip?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SLUDGE_LAYOUT


async def sludge_layout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle sludge layout selection and apply."""
    query = update.callback_query
    await query.answer()

    if query.data == 'slayout_back':
        return await show_sludge_categories(update, context)

    layout = query.data.replace('slayout_', '')
    category = context.user_data.get('sludge_category', 'subway_surfers')

    await query.edit_message_text(f"⏳ Adding retention filter...")

    input_path = context.user_data.get('input_path')
    try:
        from editors.effects import add_retention_filter
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            sludged = os.path.join(temp_dir, 'sludged.mp4')
            await add_retention_filter(input_path, sludged, category, layout)

            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(sludged, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"🎮 Retention filter ({category}) added + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Sludge filter failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


# ── Aspect Ratio Conversion ──────────────────────────────────────

async def show_aspect_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show aspect ratio conversion options."""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📱 9:16 Reel", callback_data="ar_9:16")],
        [InlineKeyboardButton("⬜ 1:1 Square", callback_data="ar_1:1")],
        [InlineKeyboardButton("🖥️ 16:9 Landscape", callback_data="ar_16:9")],
        [InlineKeyboardButton("📷 4:5 Portrait", callback_data="ar_4:5")],
        [InlineKeyboardButton("🔙 Back", callback_data="ar_back")],
    ]
    await query.edit_message_text(
        "📐 *Aspect Ratio*\n\nConvert to:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ASPECT_CONVERT


async def aspect_convert_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle aspect ratio selection."""
    query = update.callback_query
    await query.answer()

    if query.data == 'ar_back':
        return await show_overlay_options(update, context)

    from core.config import DIMENSION_PRESETS
    ratio = query.data.replace('ar_', '')
    preset = DIMENSION_PRESETS.get(ratio)
    if preset:
        context.user_data['ar_width'] = preset['width']
        context.user_data['ar_height'] = preset['height']
    else:
        context.user_data['ar_width'] = 1080
        context.user_data['ar_height'] = 1920

    keyboard = [
        [InlineKeyboardButton("✂️ Crop (cut edges)", callback_data="arm_crop")],
        [InlineKeyboardButton("⬛ Pad (black bars)", callback_data="arm_pad")],
        [InlineKeyboardButton("🌫️ Blur Background", callback_data="arm_blur")],
        [InlineKeyboardButton("🔙 Back", callback_data="arm_back")],
    ]
    await query.edit_message_text(
        f"How to handle the aspect ratio change to {ratio}?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASPECT_METHOD


async def aspect_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle aspect ratio method and apply."""
    query = update.callback_query
    await query.answer()

    if query.data == 'arm_back':
        return await show_aspect_options(update, context)

    method = query.data.replace('arm_', '')
    target_w = context.user_data.get('ar_width', 1080)
    target_h = context.user_data.get('ar_height', 1920)

    await query.edit_message_text(f"⏳ Converting aspect ratio...")

    input_path = context.user_data.get('input_path')
    try:
        from editors.effects import convert_aspect_ratio
        from core.randomizer import randomize_video

        with tempfile.TemporaryDirectory() as temp_dir:
            converted = os.path.join(temp_dir, 'converted.mp4')
            await convert_aspect_ratio(input_path, converted, target_w, target_h, method)

            final_path = os.path.join(temp_dir, 'final.mp4')
            await randomize_video(converted, final_path)

            with open(final_path, 'rb') as f:
                await query.message.reply_video(
                    video=f,
                    caption=f"📐 Converted to {target_w}x{target_h} ({method}) + randomized.",
                    supports_streaming=True
                )

        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Aspect conversion failed: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT
