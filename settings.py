import json
import os
from utils import get_voice_dir, list_voices

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

DEFAULTS = {
    "voice": None,
    "speed": 1.05,
    "noise": 0.5,
    "volume": 1.0,
    "mute": False,
    "output_device": "default",
}

def load_settings():
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to load {CONFIG_PATH}: {e}")

    voice_dir = get_voice_dir()
    available_voices = list_voices(voice_dir)
    default_voice = available_voices[0] if available_voices else "en_GB-cori-high"
    DEFAULTS["voice"] = default_voice

    settings = {**DEFAULTS, **data}

    if settings["voice"] not in available_voices:
        settings["voice"] = default_voice

    return settings

def save_settings(settings):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save settings: {e}")
        return False
