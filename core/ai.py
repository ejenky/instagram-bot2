"""AI integrations - ElevenLabs TTS, OpenAI Whisper, GPT."""

import os
import json
import asyncio
import logging
import tempfile
from typing import Optional

import httpx

from core.config import ELEVENLABS_API_KEY, OPENAI_API_KEY, VOICES_FILE

logger = logging.getLogger(__name__)


def _load_voices() -> dict:
    """Load voice ID mappings from config file."""
    if os.path.exists(VOICES_FILE):
        with open(VOICES_FILE) as f:
            return json.load(f)
    return {
        'deep_male': {'id': 'pNInz6obpgDQGcFmaJgB', 'name': 'Deep Male (Adam)'},
        'female': {'id': 'EXAVITQu4vr4xnSDxMaL', 'name': 'Female (Bella)'},
        'dramatic': {'id': 'VR6AewLTigWG4xSOukaG', 'name': 'Dramatic (Arnold)'},
        'whisper': {'id': 'MF3mGyEYCl7XYWbV9V6O', 'name': 'Soft/Whisper (Emily)'},
    }


VOICES = _load_voices()


async def text_to_speech(text: str, voice_key: str, output_path: str) -> str:
    """Generate speech audio using ElevenLabs API.

    Args:
        text: The text to speak
        voice_key: Key from VOICES dict (deep_male, female, dramatic, whisper)
        output_path: Where to save the audio file

    Returns:
        Path to the generated audio file
    """
    if not ELEVENLABS_API_KEY:
        raise Exception("ElevenLabs API key not configured. Set ELEVENLABS_API_KEY env var.")

    voice = VOICES.get(voice_key, VOICES.get('deep_male'))
    voice_id = voice['id']

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=data, headers=headers)
        if response.status_code != 200:
            logger.error(f"ElevenLabs error {response.status_code}: {response.text}")
            raise Exception(f"TTS generation failed: {response.status_code}")

        with open(output_path, 'wb') as f:
            f.write(response.content)

    return output_path


async def transcribe_audio(audio_path: str, response_format: str = 'srt') -> str:
    """Transcribe audio using OpenAI Whisper API.

    Args:
        audio_path: Path to audio file (wav, mp3, etc.)
        response_format: 'srt', 'text', 'verbose_json' (for word-level timestamps)

    Returns:
        Transcription text or SRT content
    """
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured. Set OPENAI_API_KEY env var.")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(audio_path, 'rb') as f:
            files = {
                'file': (os.path.basename(audio_path), f, 'audio/wav'),
                'model': (None, 'whisper-1'),
                'response_format': (None, response_format),
            }
            response = await client.post(url, headers=headers, files=files)

        if response.status_code != 200:
            logger.error(f"Whisper error {response.status_code}: {response.text}")
            raise Exception(f"Transcription failed: {response.status_code}")

        if response_format == 'verbose_json':
            return response.json()
        return response.text


async def transcribe_with_words(audio_path: str) -> dict:
    """Transcribe audio with word-level timestamps for animated captions.

    Returns dict with 'text' and 'words' (list of {word, start, end}).
    """
    result = await transcribe_audio(audio_path, response_format='verbose_json')
    words = []
    for segment in result.get('segments', []):
        for word_info in segment.get('words', []):
            words.append({
                'word': word_info.get('word', '').strip(),
                'start': word_info.get('start', 0),
                'end': word_info.get('end', 0),
            })
    return {
        'text': result.get('text', ''),
        'words': words,
    }


async def extract_audio(video_path: str, output_path: str) -> str:
    """Extract audio from video for transcription."""
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        output_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"Audio extraction failed: {stderr.decode()}")
        raise Exception("Audio extraction failed")

    return output_path


async def generate_caption(transcript: str) -> str:
    """Generate an engaging Instagram/TikTok caption using GPT.

    Args:
        transcript: Video transcript text

    Returns:
        Generated caption string
    """
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured. Set OPENAI_API_KEY env var.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "You generate engaging social media captions. Be concise, catchy, and relatable."
            },
            {
                "role": "user",
                "content": (
                    f"Generate an engaging Instagram caption for this video.\n"
                    f"Video transcript: {transcript}\n"
                    f"Rules:\n"
                    f"- Keep it under 150 characters\n"
                    f"- Make it relatable and catchy\n"
                    f"- Include 1-2 relevant emojis\n"
                    f"- Don't use hashtags (I'll add those separately)\n"
                    f"- Match the tone: funny, dramatic, or wholesome based on content\n"
                    f"Return ONLY the caption, nothing else."
                )
            }
        ],
        "max_tokens": 100,
        "temperature": 0.8,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=data, headers=headers)
        if response.status_code != 200:
            logger.error(f"GPT error {response.status_code}: {response.text}")
            raise Exception(f"Caption generation failed: {response.status_code}")

        result = response.json()
        return result['choices'][0]['message']['content'].strip()


async def generate_script(topic: str, style: str = 'dramatic') -> str:
    """Generate a voiceover script using GPT.

    Args:
        topic: What the video is about
        style: Script style (dramatic, funny, informative)

    Returns:
        Generated script text
    """
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured. Set OPENAI_API_KEY env var.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": f"You write short, punchy voiceover scripts for social media videos. Style: {style}."
            },
            {
                "role": "user",
                "content": (
                    f"Write a short voiceover script about: {topic}\n"
                    f"Rules:\n"
                    f"- Keep it 2-4 sentences max\n"
                    f"- Make it hook the viewer immediately\n"
                    f"- Match the {style} tone\n"
                    f"- Write it as spoken words, not text\n"
                    f"Return ONLY the script, nothing else."
                )
            }
        ],
        "max_tokens": 200,
        "temperature": 0.9,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=data, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Script generation failed: {response.status_code}")

        result = response.json()
        return result['choices'][0]['message']['content'].strip()
