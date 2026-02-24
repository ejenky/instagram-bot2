"""Template system for saving and replicating video configurations."""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TemplateManager:
    """Manages video templates - save configurations to replicate video styles."""

    def __init__(self, templates_file: str):
        self.templates_file = templates_file
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict:
        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading templates: {e}")
        return {}

    def _save_templates(self):
        os.makedirs(os.path.dirname(self.templates_file), exist_ok=True)
        with open(self.templates_file, 'w') as f:
            json.dump(self.templates, f, indent=2)

    def create_template(self, name: str, description: str, config: Dict) -> str:
        """Create a new template from a configuration dict.

        Config can include:
        - dimensions: {width, height, aspect}
        - crop_mode: str
        - dark_mode: bool
        - text_style: {font, size, color, position, shadow}
        - watermark: {type, text, position, opacity}
        - filter_preset: str
        - audio: {narration, background_music, volume}
        - clips: [{start, end, transition}]
        - text_overlays: [{text, style, timing}]
        """
        key = name.lower().replace(' ', '_')
        key = ''.join(c for c in key if c.isalnum() or c == '_')

        self.templates[key] = {
            'name': name,
            'description': description,
            'config': config,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        }
        self._save_templates()
        return key

    def update_template(self, key: str, config: Dict) -> bool:
        if key not in self.templates:
            return False
        self.templates[key]['config'].update(config)
        self.templates[key]['updated_at'] = datetime.utcnow().isoformat()
        self._save_templates()
        return True

    def delete_template(self, key: str) -> bool:
        if key in self.templates:
            del self.templates[key]
            self._save_templates()
            return True
        return False

    def get_template(self, key: str) -> Optional[Dict]:
        return self.templates.get(key)

    def list_templates(self) -> Dict:
        return self.templates

    def get_template_config(self, key: str) -> Optional[Dict]:
        """Get just the config portion of a template for applying."""
        tpl = self.templates.get(key)
        if tpl:
            return tpl.get('config', {})
        return None

    def create_from_description(self, name: str, description: str) -> str:
        """Create a template from a text description (placeholder for future AI integration).

        For now, parses key-value pairs from the description.
        """
        config = {
            'description_source': description,
            'dimensions': {'width': 1080, 'height': 1920, 'aspect': '9:16'},
            'dark_mode': True,
            'crop_mode': 'smart',
        }
        return self.create_template(name, description, config)
