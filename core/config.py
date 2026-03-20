"""Global configuration for the Content Bot."""

import os

# API Keys
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Paths
WATERMARK_IMAGE_PATH = os.getenv('WATERMARK_PATH', '/app/assets/watermark.png')
DEFAULT_WATERMARK_TEXT = os.getenv('DEFAULT_WATERMARK', '@yourusername')
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', '/tmp/content-bot/downloads')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/tmp/content-bot/output')
SLUDGE_CLIPS_DIR = os.getenv('SLUDGE_CLIPS_DIR', '/opt/content-bot/sludge-clips')
MUSIC_DIR = os.getenv('MUSIC_DIR', '/opt/content-bot/music')
FONTS_DIR = os.getenv('FONTS_DIR', '/usr/share/fonts/truetype')

PRESETS_FILE = os.path.join(DATA_DIR, 'filter_presets.json')
TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'user_settings.json')
VOICES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'voices.json')

# Limits
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE', '50'))
MAX_CONCURRENT_JOBS = 3
DOWNLOAD_TIMEOUT = 60
PROCESSING_TIMEOUT = 120

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

# Profile URL patterns (for scraping mode)
PROFILE_URL_PATTERNS = [
    r'instagram\.com/[^/]+/?$',
    r'tiktok\.com/@[^/]+/?$',
    r'twitter\.com/[^/]+/?$',
    r'x\.com/[^/]+/?$',
    r'youtube\.com/(c/|channel/|@)[^/]+/?$',
    r'pinterest\.com/[^/]+/?$',
]

# Border colors
BORDER_COLORS = {
    'black': '#000000',
    'white': '#FFFFFF',
    'red': '#FF0000',
    'blue': '#0066FF',
    'green': '#00CC00',
    'pink': '#FF69B4',
    'orange': '#FF6600',
    'purple': '#9933FF',
}

# Caption styles
CAPTION_STYLES = {
    'standard': {
        'name': 'Standard',
        'font': 'DejaVuSans-Bold.ttf',
        'fontsize': 24,
        'color': '&H00FFFFFF',
        'outline_color': '&H00000000',
        'outline': 2,
        'shadow': 1,
        'margin_v': 60,
    },
    'word_by_word': {
        'name': 'Word-by-word',
        'font': 'DejaVuSans-Bold.ttf',
        'fontsize': 32,
        'color': '&H00FFFFFF',
        'outline_color': '&H00000000',
        'outline': 3,
        'shadow': 0,
        'margin_v': 80,
    },
    'bold_pop': {
        'name': 'Bold Pop',
        'font': 'DejaVuSans-Bold.ttf',
        'fontsize': 42,
        'color': '&H0000FFFF',
        'outline_color': '&H00000000',
        'outline': 4,
        'shadow': 2,
        'margin_v': 100,
    },
    'color_wave': {
        'name': 'Color Wave',
        'font': 'DejaVuSans-Bold.ttf',
        'fontsize': 28,
        'color': '&H0000BFFF',
        'outline_color': '&H00000000',
        'outline': 2,
        'shadow': 1,
        'margin_v': 60,
    },
}

# Text overlay styles for burn-in
TEXT_STYLES = {
    'bold_white': {
        'name': 'Bold White',
        'fontcolor': 'white',
        'borderw': 3,
        'bordercolor': 'black',
    },
    'subtitle': {
        'name': 'Subtitle Style',
        'fontcolor': 'white',
        'box': 1,
        'boxcolor': 'black@0.6',
        'boxborderw': 8,
        'borderw': 0,
    },
    'meme_impact': {
        'name': 'Meme Impact',
        'fontcolor': 'white',
        'borderw': 5,
        'bordercolor': 'black',
        'fontsize_multiplier': 1.5,
    },
    'modern_clean': {
        'name': 'Modern Clean',
        'fontcolor': 'white',
        'shadowcolor': 'black@0.7',
        'shadowx': 3,
        'shadowy': 3,
        'borderw': 0,
    },
    'neon_glow': {
        'name': 'Neon Glow',
        'fontcolor': '#00FF88',
        'borderw': 4,
        'bordercolor': '#00FF88@0.3',
        'shadowcolor': '#00FF88@0.5',
        'shadowx': 0,
        'shadowy': 0,
    },
}

# Sludge clip categories
SLUDGE_CATEGORIES = {
    'subway_surfers': {'name': '🏄 Subway Surfers', 'prefix': 'subway_surfers'},
    'minecraft': {'name': '⛏️ Minecraft', 'prefix': 'minecraft_parkour'},
    'family_guy': {'name': '👨\u200d👩\u200d👦 Family Guy', 'prefix': 'family_guy'},
    'gta': {'name': '🎮 GTA', 'prefix': 'gta'},
    'satisfying': {'name': '🧼 Satisfying', 'prefix': 'satisfying'},
}

# Speed presets
SPEED_PRESETS = {
    '0.5x': 0.5,
    '0.75x': 0.75,
    '1.5x': 1.5,
    '2x': 2.0,
    '3x': 3.0,
}

# Voice effect presets
VOICE_EFFECTS = {
    'deep': {'name': '🔊 Deep Voice', 'rate': 0.8, 'tempo': 1.25},
    'chipmunk': {'name': '🐿️ Chipmunk', 'rate': 1.4, 'tempo': 0.714},
    'echo': {'name': '🔁 Echo', 'filter': 'aecho=0.8:0.88:60:0.4'},
    'robot': {'name': '🤖 Robot', 'filter': "afftfilt=real='hypot(re,im)*sin(0)':imag='hypot(re,im)*cos(0)':win_size=512:overlap=0.75"},
}

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
    # Ranking video states
    RANKING_MENU,           # 23 - ranking item count
    RANKING_TITLE,          # 24 - enter title
    RANKING_COLORS,         # 25 - assign word colors
    RANKING_CLIPS,          # 26 - send clips
    RANKING_LABELS,         # 27 - enter labels
    RANKING_AUDIO,          # 28 - background music
    RANKING_PREVIEW,        # 29 - post-build actions
    # ── New states for content bot features ──
    DOWNLOAD_ACTIONS,       # 30 - action menu after download
    OVERLAY_MENU,           # 31 - overlay type selection
    BORDER_COLOR,           # 32 - pick border color
    BORDER_CUSTOM_HEX,      # 33 - enter custom hex color
    CAPTION_TEXT,            # 34 - enter caption text
    CAPTION_POSITION,       # 35 - caption position
    CAPTION_STYLE,          # 36 - caption style
    SLUDGE_CATEGORY,        # 37 - sludge clip category
    SLUDGE_LAYOUT,          # 38 - sludge layout
    TEMPLATE_CHOICE,        # 39 - template format selection
    ASPECT_CONVERT,         # 40 - aspect ratio conversion
    ASPECT_METHOD,          # 41 - crop/pad/blur method
    AUTO_CAPTION_STYLE,     # 42 - auto caption style selection
    VOICEOVER_TEXT,          # 43 - voiceover script input
    VOICEOVER_VOICE,        # 44 - voice selection
    VOICEOVER_MODE,         # 45 - replace or mix audio
    SPEED_SELECT,           # 46 - speed selection
    VOICE_EFFECT_SELECT,    # 47 - voice effect selection
    MUSIC_CATEGORY,         # 48 - music category
    MUSIC_SELECT,           # 49 - music track selection
    FULL_PROCESS_CONFIRM,   # 50 - confirm full process
    SETTINGS_MENU,          # 51 - settings menu
    BATCH_PROCESSING,       # 52 - batch URL processing
    SLIDESHOW_IMAGES,       # 53 - collect images for slideshow
    PROFILE_SCRAPE,         # 54 - profile scraping options
    TEXT_INPUT_ACTION,       # 55 - handle plain text input
    # ── Tweet pipeline states ──
    PAGE_SELECT,             # 56 - page selector (reversedworlds, cattos.jpeg, etc.)
    TWEET_RATIO,             # 57 - format ratio selection
    TWEET_BG_COLOR,          # 58 - background color selection
    TWEET_XLOGO,             # 59 - color out X logo yes/no
) = range(60)
