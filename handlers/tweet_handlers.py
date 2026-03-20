"""Handlers for the tweet content pipeline (reversedworlds, cattos.jpeg, etc.).

When a user sends a Twitter/X tweet URL, shows a page selector, then walks through
format ratio, background color, and X logo options before processing the image.
"""

import os
import re
import shutil
import tempfile
import logging

from PIL import Image, ImageDraw

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    DATA_DIR, WAITING_FOR_CONTENT,
    PAGE_SELECT, TWEET_RATIO, TWEET_BG_COLOR, TWEET_XLOGO,
)
from core.downloader import MediaDownloader

logger = logging.getLogger(__name__)

# Dimensions for each format ratio
TWEET_DIMENSIONS = {
    '4:5': (1080, 1350),
    '1:1': (1080, 1080),
    '9:16': (1080, 1920),
}


def is_tweet_url(url: str) -> bool:
    """Check if URL is a Twitter/X tweet link (contains /status/)."""
    return bool(re.search(r'(twitter\.com|x\.com)/[^/]+/status/', url))


async def show_page_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show page selector buttons after detecting a tweet URL."""
    keyboard = [
        [InlineKeyboardButton("reversedworlds", callback_data="tw_page_reversedworlds")],
        [InlineKeyboardButton("cattos.jpeg", callback_data="tw_page_cattos")],
        [InlineKeyboardButton("lube", callback_data="tw_page_lube")],
        [InlineKeyboardButton("laxative", callback_data="tw_page_laxative")],
    ]
    msg = update.message
    await msg.reply_text(
        "Select a page:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return PAGE_SELECT


async def page_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle page selection."""
    query = update.callback_query
    await query.answer()

    page = query.data.replace("tw_page_", "")

    if page != "reversedworlds":
        await query.edit_message_text("Coming soon!")
        context.user_data.clear()
        return WAITING_FOR_CONTENT

    # reversedworlds flow — ask format ratio
    context.user_data['tw_page'] = page
    keyboard = [
        [
            InlineKeyboardButton("4:5", callback_data="tw_ratio_4:5"),
            InlineKeyboardButton("1:1", callback_data="tw_ratio_1:1"),
            InlineKeyboardButton("9:16", callback_data="tw_ratio_9:16"),
        ],
    ]
    await query.edit_message_text(
        "Format ratio:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TWEET_RATIO


async def tweet_ratio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle format ratio selection."""
    query = update.callback_query
    await query.answer()

    ratio = query.data.replace("tw_ratio_", "")
    context.user_data['tw_ratio'] = ratio

    keyboard = [
        [
            InlineKeyboardButton("Black", callback_data="tw_bg_black"),
            InlineKeyboardButton("White", callback_data="tw_bg_white"),
        ],
    ]
    await query.edit_message_text(
        "Background color:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TWEET_BG_COLOR


async def tweet_bg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle background color selection."""
    query = update.callback_query
    await query.answer()

    color = query.data.replace("tw_bg_", "")
    context.user_data['tw_bg'] = color

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data="tw_xlogo_yes"),
            InlineKeyboardButton("No", callback_data="tw_xlogo_no"),
        ],
    ]
    await query.edit_message_text(
        "Color out X logo?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TWEET_XLOGO


async def tweet_xlogo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle X logo choice, then download + process the tweet image."""
    query = update.callback_query
    await query.answer()

    color_out_logo = query.data == "tw_xlogo_yes"
    url = context.user_data.get('tw_url', '')
    ratio = context.user_data.get('tw_ratio', '4:5')
    bg_color = context.user_data.get('tw_bg', 'black')

    await query.edit_message_text("Downloading tweet...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download tweet media
            downloader = MediaDownloader(temp_dir)
            result = await downloader.download(url)

            src_path = result['path']
            # If gallery, take the first file
            if result.get('type') == 'gallery' and result.get('files'):
                src_path = result['files'][0]

            await query.message.edit_text("Processing image...")

            # Process with Pillow
            canvas_w, canvas_h = TWEET_DIMENSIONS.get(ratio, (1080, 1350))
            fill = (0, 0, 0) if bg_color == 'black' else (255, 255, 255)

            screenshot = Image.open(src_path).convert('RGBA')

            # Color out X logo if requested (top-right ~50x50 area)
            if color_out_logo:
                draw = ImageDraw.Draw(screenshot)
                sw, sh = screenshot.size
                draw.rectangle(
                    [sw - 50, 0, sw, 50],
                    fill=fill + (255,),
                )

            # Create canvas and paste centered
            canvas = Image.new('RGBA', (canvas_w, canvas_h), fill + (255,))

            # Scale screenshot to fit within canvas with padding
            sw, sh = screenshot.size
            max_w = canvas_w - 40   # 20px padding each side
            max_h = canvas_h - 40

            scale = min(max_w / sw, max_h / sh, 1.0)
            new_w = int(sw * scale)
            new_h = int(sh * scale)

            if scale < 1.0:
                screenshot = screenshot.resize((new_w, new_h), Image.LANCZOS)

            paste_x = (canvas_w - new_w) // 2
            paste_y = (canvas_h - new_h) // 2

            canvas.paste(screenshot, (paste_x, paste_y), screenshot)

            # Save as PNG
            output_path = os.path.join(DATA_DIR, f'tweet_{query.from_user.id}.png')
            canvas.convert('RGB').save(output_path, 'PNG')

            with open(output_path, 'rb') as f:
                await query.message.reply_photo(photo=f)

            # Cleanup
            os.remove(output_path)

        context.user_data.clear()
        await query.message.reply_text("Send another link or file!")
        return WAITING_FOR_CONTENT

    except Exception as e:
        logger.error(f"Tweet processing failed: {e}", exc_info=True)
        await query.message.reply_text(f"Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT
