"""Global configuration for the Instagram Content Bot."""

import os

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
WATERMARK_IMAGE_PATH = os.getenv('WATERMARK_PATH', '/app/assets/watermark.png')
DEFAULT_WATERMARK_TEXT = os.getenv('DEFAULT_WATERMARK', '@yourusername')
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
PRESETS_FILE = os.path.join(DATA_DIR, 'filter_presets.json')
TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')

# Instagram Reels dimensions (default)
REEL_WIDTH = 1080
REEL_HEIGHT = 1920

# Supported output dimension presets
DIMENSION_PRESETS = {
    '9:16': {'width': 1080, 'height': 1920, 'label': '9:16 (Reels/TikTok)'},
    '1:1': {'width': 1080, 'height': 1080, 'label': '1:1 (Square)'},
    '4:5': {'width': 1080, 'height': 1350, 'label': '4:5 (Portrait)'},
    '16:9': {'width': 1920, 'height': 1080, 'label': '16:9 (Landscape)'},
    '4:3': {'width': 1440, 'height': 1080, 'label': '4:3 (Classic)'},
}

# Supported social media domains for auto-download
SUPPORTED_DOMAINS = [
    'twitter.com', 'x.com', 'tiktok.com', 'instagram.com',
    'youtube.com', 'youtu.be', 'facebook.com', 'fb.watch',
    'reddit.com', 'v.redd.it', 'streamable.com', 'vimeo.com',
    'dailymotion.com', 'twitch.tv', 'clips.twitch.tv',
    'pinterest.com', 'pin.it', 'tumblr.com', 'snapchat.com',
    'linkedin.com',
]

# Conversation states
(
    WAITING_FOR_CONTENT,    # 0 - waiting for link/file
    ACTION_CHOICE,          # 1 - edit or create?
    CHOOSE_CROP,            # 2 - crop mode
    CHOOSE_DIMENSIONS,      # 3 - output dimensions
    CHOOSE_MODE,            # 4 - dark/light
    ENTER_TEXT,             # 5 - add text?
    CONFIRM_TEXT,           # 6 - confirm text
    CHOOSE_WATERMARK,       # 7 - watermark options
    ENTER_WATERMARK_TEXT,   # 8 - custom watermark text
    CHOOSE_FILTER,          # 9 - filter preset
    MANAGE_PRESETS,         # 10 - preset management
    CREATE_PRESET,          # 11 - create preset
    PROCESS_CONTENT,        # 12 - processing
    # Video creation states
    CREATE_MENU,            # 13 - creation main menu
    CREATE_ADD_CLIPS,       # 14 - add clips to timeline
    CREATE_TEXT_STYLE,      # 15 - text styling
    CREATE_AUDIO,           # 16 - audio/narration
    CREATE_PREVIEW,         # 17 - preview creation
    # Template states
    TEMPLATE_MENU,          # 18 - template management
    TEMPLATE_NAME,          # 19 - name template
    TEMPLATE_DESCRIBE,      # 20 - describe template
    TEMPLATE_SELECT,        # 21 - select template to use
    # Edit prompt (after download)
    EDIT_PROMPT,            # 22 - ask if user wants to edit
) = range(23)
