"""Handlers for the video creation flow (CapCut-like)."""

import os
import tempfile
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import (
    DATA_DIR, DIMENSION_PRESETS,
    WAITING_FOR_CONTENT, CREATE_MENU, CREATE_ADD_CLIPS,
    CREATE_TEXT_STYLE, CREATE_AUDIO, CREATE_PREVIEW,
)
from core.media_info import get_media_info
from creators.video_creator import VideoCreator, TextStyle, ClipSegment

logger = logging.getLogger(__name__)


async def create_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show the main creation menu."""
    # Initialize creator if not exists
    if 'creator' not in context.user_data:
        context.user_data['creator'] = VideoCreator(
            tempfile.mkdtemp(prefix='creator_')
        )

    creator = context.user_data['creator']
    clip_count = len(creator.clips)
    text_count = len(creator.text_overlays)

    status_lines = [
        f"*Video Creator*\n",
        f"Clips: {clip_count}",
        f"Text overlays: {text_count}",
        f"Background audio: {'Yes' if creator.background_audio else 'No'}",
        f"Narration: {'Yes' if creator.narration_audio else 'No'}",
        f"Dimensions: {creator.target_width}x{creator.target_height}",
    ]

    keyboard = [
        [InlineKeyboardButton("Add Clip", callback_data="create_add_clip")],
        [
            InlineKeyboardButton("Add Text", callback_data="create_add_text"),
            InlineKeyboardButton("Text Styles", callback_data="create_text_styles"),
        ],
        [
            InlineKeyboardButton("Set Audio", callback_data="create_audio"),
            InlineKeyboardButton("Dimensions", callback_data="create_dimensions"),
        ],
        [InlineKeyboardButton("Preview & Build", callback_data="create_build")],
        [
            InlineKeyboardButton("Save as Template", callback_data="create_save_template"),
            InlineKeyboardButton("Load Template", callback_data="create_load_template"),
        ],
        [InlineKeyboardButton("Listicle / Ranking", callback_data="create_listicle")],
        [InlineKeyboardButton("Clear All", callback_data="create_clear")],
        [InlineKeyboardButton("Cancel", callback_data="create_cancel")],
    ]

    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            '\n'.join(status_lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif msg:
        await msg.reply_text(
            '\n'.join(status_lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    return CREATE_MENU


async def create_add_clip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle adding clips to the timeline."""
    query = update.callback_query
    msg = update.message

    if query:
        await query.answer()
        action = query.data

        if action == "create_add_clip":
            await query.edit_message_text(
                "*Add a clip*\n\n"
                "Send me:\n"
                "- A video file\n"
                "- A social media link\n"
                "- An image (will be shown for 3 seconds)\n\n"
                "After uploading, you can set trim points and speed.\n\n"
                "Send /done when finished adding clips.",
                parse_mode='Markdown'
            )
            return CREATE_ADD_CLIPS

        elif action == "create_clip_trim":
            await query.edit_message_text(
                "Enter trim points as: `start end`\n"
                "Example: `0 5.5` (first 5.5 seconds)\n"
                "Or `3 10` (from 3s to 10s)\n\n"
                "Send `skip` to use the full clip.",
                parse_mode='Markdown'
            )
            return CREATE_ADD_CLIPS

        elif action == "create_clip_speed":
            keyboard = [
                [
                    InlineKeyboardButton("0.5x", callback_data="speed_0.5"),
                    InlineKeyboardButton("0.75x", callback_data="speed_0.75"),
                    InlineKeyboardButton("1x", callback_data="speed_1.0"),
                ],
                [
                    InlineKeyboardButton("1.25x", callback_data="speed_1.25"),
                    InlineKeyboardButton("1.5x", callback_data="speed_1.5"),
                    InlineKeyboardButton("2x", callback_data="speed_2.0"),
                ],
            ]
            await query.edit_message_text(
                "Select clip speed:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CREATE_ADD_CLIPS

        elif action.startswith("speed_"):
            speed = float(action.replace("speed_", ""))
            if 'pending_clip' in context.user_data:
                context.user_data['pending_clip']['speed'] = speed
                # Finalize clip
                clip_data = context.user_data.pop('pending_clip')
                creator = context.user_data.get('creator')
                if creator:
                    creator.add_clip(ClipSegment(
                        source_path=clip_data['path'],
                        start_time=clip_data.get('start', 0),
                        end_time=clip_data.get('end'),
                        speed=speed,
                        transition=clip_data.get('transition', 'none'),
                    ))
                await query.edit_message_text(
                    f"Clip added! (speed: {speed}x)\n"
                    f"Total clips: {len(creator.clips)}\n\n"
                    "Send another clip or /done to go back to the menu."
                )
            return CREATE_ADD_CLIPS

        elif action == "create_clip_transition":
            keyboard = [
                [
                    InlineKeyboardButton("None", callback_data="trans_none"),
                    InlineKeyboardButton("Fade", callback_data="trans_fade"),
                ],
                [
                    InlineKeyboardButton("Dissolve", callback_data="trans_dissolve"),
                    InlineKeyboardButton("Wipe", callback_data="trans_wipe_left"),
                ],
            ]
            await query.edit_message_text(
                "Select transition to next clip:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CREATE_ADD_CLIPS

        elif action.startswith("trans_"):
            trans = action.replace("trans_", "")
            if 'pending_clip' in context.user_data:
                context.user_data['pending_clip']['transition'] = trans
            keyboard = [
                [
                    InlineKeyboardButton("Set Speed", callback_data="create_clip_speed"),
                    InlineKeyboardButton("Add Clip (default speed)", callback_data="speed_1.0"),
                ],
            ]
            await query.edit_message_text(
                f"Transition: *{trans}*\n\nSet speed or add with default:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return CREATE_ADD_CLIPS

        elif action in ["create_add_text", "create_text_styles"]:
            return await create_text_handler(update, context)
        elif action == "create_audio":
            return await create_audio_handler(update, context)
        elif action == "create_build":
            return await create_preview_handler(update, context)
        elif action == "create_clear":
            if 'creator' in context.user_data:
                context.user_data['creator'].clear_timeline()
            await query.edit_message_text("Timeline cleared.")
            return await create_menu(update, context)
        elif action == "create_listicle":
            from handlers.listicle_handlers import listicle_start
            return await listicle_start(update, context)

        elif action == "create_cancel":
            context.user_data.pop('creator', None)
            await query.edit_message_text("Creation cancelled. Send a link or file to start editing.")
            return WAITING_FOR_CONTENT
        elif action == "create_dimensions":
            keyboard = []
            row = []
            for key, preset in DIMENSION_PRESETS.items():
                row.append(InlineKeyboardButton(preset['label'], callback_data=f"cdim_{key}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            await query.edit_message_text(
                "Select output dimensions:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return CREATE_MENU

        elif action.startswith("cdim_"):
            dim_key = action.replace("cdim_", "")
            preset = DIMENSION_PRESETS.get(dim_key)
            if preset and 'creator' in context.user_data:
                context.user_data['creator'].target_width = preset['width']
                context.user_data['creator'].target_height = preset['height']
            return await create_menu(update, context)

        elif action == "create_save_template":
            from handlers.template_handlers import template_name_handler
            await query.edit_message_text("Enter a name for this template:")
            context.user_data['template_source'] = 'creator'
            from core.config import TEMPLATE_NAME
            return TEMPLATE_NAME

        elif action == "create_load_template":
            from handlers.template_handlers import template_menu
            return await template_menu(update, context)

    elif msg:
        # User sent a file/link - add as clip
        creator = context.user_data.get('creator')
        if not creator:
            context.user_data['creator'] = VideoCreator(tempfile.mkdtemp(prefix='creator_'))
            creator = context.user_data['creator']

        if msg.text:
            text = msg.text.strip()
            if text == '/done':
                return await create_menu(update, context)

            # Check for trim points
            if 'pending_clip' in context.user_data:
                parts = text.split()
                if text.lower() == 'skip':
                    context.user_data['pending_clip']['start'] = 0
                    context.user_data['pending_clip']['end'] = None
                elif len(parts) == 2:
                    try:
                        start = float(parts[0])
                        end = float(parts[1])
                        context.user_data['pending_clip']['start'] = start
                        context.user_data['pending_clip']['end'] = end
                    except ValueError:
                        await msg.reply_text("Invalid format. Use: `start end` (e.g. `0 5.5`)", parse_mode='Markdown')
                        return CREATE_ADD_CLIPS

                keyboard = [
                    [
                        InlineKeyboardButton("Set Transition", callback_data="create_clip_transition"),
                        InlineKeyboardButton("Set Speed", callback_data="create_clip_speed"),
                    ],
                    [InlineKeyboardButton("Add with Defaults", callback_data="speed_1.0")],
                ]
                await msg.reply_text(
                    "Trim set. Choose next option:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return CREATE_ADD_CLIPS

            # Try downloading as link
            from core.downloader import MediaDownloader
            if MediaDownloader.is_supported_url(text):
                await msg.reply_text("Downloading...")
                try:
                    with tempfile.TemporaryDirectory() as td:
                        downloader = MediaDownloader(td)
                        result = await downloader.download(text)
                        # Copy to persistent location
                        persistent = os.path.join(
                            DATA_DIR,
                            f'clip_{msg.from_user.id}_{len(creator.clips)}.mp4'
                        )
                        import shutil
                        shutil.copy2(result['path'], persistent)

                    context.user_data['pending_clip'] = {
                        'path': persistent,
                        'start': 0,
                        'end': None,
                        'speed': 1.0,
                        'transition': 'none',
                    }

                    info = get_media_info(persistent)
                    duration = info.get('duration', 0)

                    keyboard = [
                        [InlineKeyboardButton("Trim Clip", callback_data="create_clip_trim")],
                        [InlineKeyboardButton("Set Transition", callback_data="create_clip_transition")],
                        [InlineKeyboardButton("Set Speed", callback_data="create_clip_speed")],
                        [InlineKeyboardButton("Add with Defaults", callback_data="speed_1.0")],
                    ]
                    await msg.reply_text(
                        f"Downloaded! Duration: {duration:.1f}s\n\nConfigure this clip:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    await msg.reply_text(f"Download failed: {e}")
                return CREATE_ADD_CLIPS

        elif msg.video or msg.document:
            file = await (msg.video or msg.document).get_file()
            ext = 'mp4'
            if msg.document and msg.document.file_name:
                ext = msg.document.file_name.split('.')[-1]
            path = os.path.join(DATA_DIR, f'clip_{msg.from_user.id}_{len(creator.clips)}.{ext}')
            await file.download_to_drive(path)

            context.user_data['pending_clip'] = {
                'path': path,
                'start': 0,
                'end': None,
                'speed': 1.0,
                'transition': 'none',
            }

            info = get_media_info(path)
            duration = info.get('duration', 0)

            keyboard = [
                [InlineKeyboardButton("Trim Clip", callback_data="create_clip_trim")],
                [InlineKeyboardButton("Set Transition", callback_data="create_clip_transition")],
                [InlineKeyboardButton("Set Speed", callback_data="create_clip_speed")],
                [InlineKeyboardButton("Add with Defaults", callback_data="speed_1.0")],
            ]
            await msg.reply_text(
                f"Clip received! Duration: {duration:.1f}s\n\nConfigure this clip:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CREATE_ADD_CLIPS

        elif msg.photo:
            photo = msg.photo[-1]
            file = await photo.get_file()
            path = os.path.join(DATA_DIR, f'clip_{msg.from_user.id}_{len(creator.clips)}.jpg')
            await file.download_to_drive(path)

            # Images become 3-second still clips
            context.user_data['pending_clip'] = {
                'path': path,
                'start': 0,
                'end': 3,
                'speed': 1.0,
                'transition': 'none',
            }

            keyboard = [
                [InlineKeyboardButton("Set Transition", callback_data="create_clip_transition")],
                [InlineKeyboardButton("Add with Defaults", callback_data="speed_1.0")],
            ]
            await msg.reply_text(
                "Image received! Will display for 3 seconds.\n\nConfigure:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CREATE_ADD_CLIPS

    return CREATE_ADD_CLIPS


async def create_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle adding text overlays to the creation."""
    query = update.callback_query
    msg = update.message

    if query:
        await query.answer()
        action = query.data

        if action in ["create_add_text", "create_text_styles"]:
            # Show text styling options
            keyboard = [
                [InlineKeyboardButton("Add New Text", callback_data="text_new")],
                [
                    InlineKeyboardButton("Bold", callback_data="tfont_bold"),
                    InlineKeyboardButton("Regular", callback_data="tfont_regular"),
                ],
                [
                    InlineKeyboardButton("Mono", callback_data="tfont_mono"),
                    InlineKeyboardButton("Serif", callback_data="tfont_serif"),
                ],
            ]

            # Show color palette
            color_row = []
            for color_name in ['white', 'red', 'yellow', 'neon_green']:
                color_row.append(
                    InlineKeyboardButton(color_name.title(), callback_data=f"tcolor_{color_name}")
                )
            keyboard.append(color_row)

            color_row2 = []
            for color_name in ['blue', 'pink', 'orange', 'cyan']:
                color_row2.append(
                    InlineKeyboardButton(color_name.title(), callback_data=f"tcolor_{color_name}")
                )
            keyboard.append(color_row2)

            keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="create_back")])

            creator = context.user_data.get('creator')
            overlay_info = ""
            if creator and creator.text_overlays:
                overlay_info = "\n\nCurrent text overlays:"
                for i, t in enumerate(creator.text_overlays):
                    overlay_info += f"\n{i + 1}. \"{t.text}\" ({t.font}, {t.color})"

            await query.edit_message_text(
                f"*Text Styles*{overlay_info}\n\n"
                "Select a font, then color, then enter your text.\n"
                "Or tap 'Add New Text' for quick add.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return CREATE_TEXT_STYLE

        elif action == "text_new":
            context.user_data['text_font'] = 'bold'
            context.user_data['text_color'] = 'white'
            await query.edit_message_text(
                "Enter the text to add:\n\n"
                "You can also specify position after text:\n"
                "`Your text here | top`\n"
                "`Your text here | bottom`\n"
                "`Your text here | center`\n\n"
                "Or for timed text:\n"
                "`Your text here | center | 0 5`\n"
                "(shows from 0s to 5s)",
                parse_mode='Markdown'
            )
            return CREATE_TEXT_STYLE

        elif action.startswith("tfont_"):
            context.user_data['text_font'] = action.replace("tfont_", "")
            await query.edit_message_text(
                f"Font: *{context.user_data['text_font']}*\n\n"
                "Now enter the text (with optional position and timing):\n"
                "`Your text | position | start end`",
                parse_mode='Markdown'
            )
            return CREATE_TEXT_STYLE

        elif action.startswith("tcolor_"):
            context.user_data['text_color'] = action.replace("tcolor_", "")
            await query.edit_message_text(
                f"Color: *{context.user_data['text_color']}*\n\n"
                "Now enter the text (with optional position and timing):\n"
                "`Your text | position | start end`",
                parse_mode='Markdown'
            )
            return CREATE_TEXT_STYLE

        elif action == "create_back":
            return await create_menu(update, context)

    elif msg:
        text = msg.text.strip()
        if text == '/done':
            return await create_menu(update, context)

        # Parse: text | position | start end
        parts = [p.strip() for p in text.split('|')]
        display_text = parts[0]
        position = 'center'
        start_time = 0.0
        end_time = None

        if len(parts) >= 2:
            pos = parts[1].lower()
            if pos in ['top', 'bottom', 'center']:
                position = pos

        if len(parts) >= 3:
            timing = parts[2].split()
            if len(timing) == 2:
                try:
                    start_time = float(timing[0])
                    end_time = float(timing[1])
                except ValueError:
                    pass

        font = context.user_data.get('text_font', 'bold')
        color = context.user_data.get('text_color', 'white')

        creator = context.user_data.get('creator')
        if creator:
            creator.add_text(TextStyle(
                text=display_text,
                font=font,
                size=58,
                color=color,
                position=position,
                shadow=True,
                start_time=start_time,
                end_time=end_time,
            ))
            await msg.reply_text(
                f"Text added: \"{display_text}\"\n"
                f"Font: {font}, Color: {color}, Position: {position}\n"
                f"{'Timing: ' + str(start_time) + 's - ' + str(end_time) + 's' if end_time else 'Shows entire video'}\n\n"
                "Send more text or /done to go back."
            )
        return CREATE_TEXT_STYLE

    return CREATE_TEXT_STYLE


async def create_audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle audio settings for video creation."""
    query = update.callback_query
    msg = update.message

    if query:
        await query.answer()
        action = query.data

        if action == "create_audio":
            keyboard = [
                [InlineKeyboardButton("Add Background Music", callback_data="audio_bg")],
                [InlineKeyboardButton("Add Narration", callback_data="audio_narration")],
                [InlineKeyboardButton("Remove Audio", callback_data="audio_remove")],
                [InlineKeyboardButton("Back to Menu", callback_data="create_back")],
            ]
            creator = context.user_data.get('creator')
            status = ""
            if creator:
                if creator.background_audio:
                    status += f"\nBackground: Set (vol: {creator.bg_audio_volume})"
                if creator.narration_audio:
                    status += f"\nNarration: Set (vol: {creator.narration_volume})"

            await query.edit_message_text(
                f"*Audio Settings*{status}\n\n"
                "Send audio files for background music or narration.\n"
                "For AI narration (ElevenLabs-style), send the text after selecting narration mode.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return CREATE_AUDIO

        elif action == "audio_bg":
            context.user_data['audio_mode'] = 'background'
            keyboard = [
                [
                    InlineKeyboardButton("0.1", callback_data="bgvol_0.1"),
                    InlineKeyboardButton("0.2", callback_data="bgvol_0.2"),
                    InlineKeyboardButton("0.3", callback_data="bgvol_0.3"),
                ],
                [
                    InlineKeyboardButton("0.5", callback_data="bgvol_0.5"),
                    InlineKeyboardButton("0.7", callback_data="bgvol_0.7"),
                    InlineKeyboardButton("1.0", callback_data="bgvol_1.0"),
                ],
            ]
            await query.edit_message_text(
                "Select background music volume (relative to main audio):",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CREATE_AUDIO

        elif action.startswith("bgvol_"):
            vol = float(action.replace("bgvol_", ""))
            creator = context.user_data.get('creator')
            if creator:
                creator.bg_audio_volume = vol
            await query.edit_message_text(
                f"Volume: {vol}\n\nNow send the audio file for background music."
            )
            return CREATE_AUDIO

        elif action == "audio_narration":
            context.user_data['audio_mode'] = 'narration'
            await query.edit_message_text(
                "*Narration*\n\n"
                "Send an audio file for narration.\n\n"
                "Note: For AI-generated narration (ElevenLabs), "
                "generate the audio externally and upload it here.\n"
                "Future updates will integrate TTS directly.",
                parse_mode='Markdown'
            )
            return CREATE_AUDIO

        elif action == "audio_remove":
            creator = context.user_data.get('creator')
            if creator:
                creator.background_audio = None
                creator.narration_audio = None
            await query.edit_message_text("Audio cleared.")
            return await create_menu(update, context)

        elif action == "create_back":
            return await create_menu(update, context)

    elif msg:
        if msg.text and msg.text.strip() == '/done':
            return await create_menu(update, context)

        # Handle audio file upload
        if msg.audio or msg.voice or msg.document:
            file = await (msg.audio or msg.voice or msg.document).get_file()
            ext = 'mp3'
            if msg.document and msg.document.file_name:
                ext = msg.document.file_name.split('.')[-1]
            audio_mode = context.user_data.get('audio_mode', 'background')
            path = os.path.join(DATA_DIR, f'{audio_mode}_{msg.from_user.id}.{ext}')
            await file.download_to_drive(path)

            creator = context.user_data.get('creator')
            if creator:
                if audio_mode == 'background':
                    creator.set_background_audio(path, creator.bg_audio_volume)
                else:
                    creator.set_narration(path)

            await msg.reply_text(
                f"{'Background music' if audio_mode == 'background' else 'Narration'} set!\n"
                "Send /done to go back to the menu."
            )
            return CREATE_AUDIO

    return CREATE_AUDIO


async def create_preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Build and preview the created video."""
    query = update.callback_query
    if query:
        await query.answer()

    creator = context.user_data.get('creator')
    if not creator or not creator.clips:
        msg = query.message if query else update.message
        await msg.reply_text("No clips in timeline. Add at least one clip first.")
        return await create_menu(update, context)

    msg = query.message if query else update.message
    status = await msg.reply_text("Building video...\nThis may take a moment.")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Update creator temp dir
            creator.temp_dir = temp_dir
            rand = creator._random_str()
            output_path = os.path.join(temp_dir, f'created_{rand}.mp4')

            await status.edit_text(
                f"Building video...\n"
                f"Processing {len(creator.clips)} clips..."
            )

            await creator.create(output_path)

            await status.edit_text("Uploading...")
            with open(output_path, 'rb') as f:
                await msg.reply_video(
                    video=f,
                    caption=(
                        f"Video created!\n"
                        f"Clips: {len(creator.clips)} | "
                        f"Text overlays: {len(creator.text_overlays)} | "
                        f"Dimensions: {creator.target_width}x{creator.target_height}"
                    ),
                    supports_streaming=True
                )

        await status.delete()

        keyboard = [
            [
                InlineKeyboardButton("Save as Template", callback_data="create_save_template"),
                InlineKeyboardButton("Create Another", callback_data="create_new"),
            ],
            [InlineKeyboardButton("Done", callback_data="create_done")],
        ]
        await msg.reply_text(
            "What would you like to do?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CREATE_PREVIEW

    except Exception as e:
        logger.error(f"Video creation failed: {e}", exc_info=True)
        await status.edit_text(f"Build failed: {e}")
        return await create_menu(update, context)
