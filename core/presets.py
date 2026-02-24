"""Filter preset management."""

import os
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PresetManager:
    DEFAULT_PRESETS = {
        "vibrant": {
            "name": "Vibrant",
            "description": "Boosted saturation and contrast",
            "filters": {"saturation": 1.4, "contrast": 1.2, "brightness": 1.05}
        },
        "muted": {
            "name": "Muted",
            "description": "Subtle, desaturated look",
            "filters": {"saturation": 0.7, "contrast": 0.95, "brightness": 1.0}
        },
        "warm": {
            "name": "Warm",
            "description": "Warm orange tones",
            "filters": {"saturation": 1.1, "contrast": 1.1, "brightness": 1.02, "temperature": 30}
        },
        "cool": {
            "name": "Cool",
            "description": "Cool blue tones",
            "filters": {"saturation": 1.05, "contrast": 1.1, "brightness": 1.0, "temperature": -30}
        },
        "high_contrast": {
            "name": "High Contrast",
            "description": "Punchy blacks and whites",
            "filters": {"saturation": 1.1, "contrast": 1.4, "brightness": 1.0}
        },
        "faded": {
            "name": "Faded",
            "description": "Lifted blacks, vintage feel",
            "filters": {"saturation": 0.85, "contrast": 0.85, "brightness": 1.05, "black_point": 30}
        },
        "none": {
            "name": "No Filter",
            "description": "Original image",
            "filters": {}
        }
    }

    def __init__(self, presets_file: str):
        self.presets_file = presets_file
        self.presets = self._load_presets()

    def _load_presets(self) -> Dict:
        presets = self.DEFAULT_PRESETS.copy()
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r') as f:
                    presets.update(json.load(f))
            except Exception as e:
                logger.error(f"Error loading presets: {e}")
        return presets

    def save_presets(self):
        os.makedirs(os.path.dirname(self.presets_file), exist_ok=True)
        custom = {k: v for k, v in self.presets.items() if k not in self.DEFAULT_PRESETS}
        with open(self.presets_file, 'w') as f:
            json.dump(custom, f, indent=2)

    def add_preset(self, key: str, name: str, description: str, filters: Dict):
        self.presets[key] = {"name": name, "description": description, "filters": filters}
        self.save_presets()

    def delete_preset(self, key: str) -> bool:
        if key in self.DEFAULT_PRESETS:
            return False
        if key in self.presets:
            del self.presets[key]
            self.save_presets()
            return True
        return False

    def get_preset(self, key: str) -> Optional[Dict]:
        return self.presets.get(key)

    def list_presets(self) -> Dict:
        return self.presets
