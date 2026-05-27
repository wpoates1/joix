import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

CURRENT_JOIX_FILE = DATA_DIR / "current_joix.json"
HISTORY_FILE = DATA_DIR / "history.json"

def get_config():
    """Returns the current application configuration loaded from environment variables."""
    return {
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "spotify_client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "spotify_client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
        "spotify_redirect_uri": os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback"),
        "elevenlabs_api_key": os.getenv("ELEVENLABS_API_KEY"),
        "elevenlabs_voice_id": os.getenv("ELEVENLABS_VOICE_ID"),
        "playlist_master_name": os.getenv("PLAYLIST_MASTER_NAME", "JOIX Master"),
    }

def load_current_joix():
    """Loads the active JOIX workspace state from current_joix.json."""
    if not CURRENT_JOIX_FILE.exists():
        return None
    try:
        with open(CURRENT_JOIX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_current_joix(data):
    """Saves the active JOIX workspace state to current_joix.json."""
    with open(CURRENT_JOIX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data

def load_history():
    """Loads the history of published JOIX playlists."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history(history_data):
    """Saves the history of published JOIX playlists."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)
    return history_data

def add_to_history(joix_data):
    """Adds a published JOIX item to history and clears/archives current_joix."""
    history = load_history()
    # Check if already exists in history to avoid duplicates
    history = [item for item in history if item.get("id") != joix_data.get("id")]
    history.append(joix_data)
    save_history(history)
    
    # Save active as a historical snapshot file as well
    snapshot_dir = DATA_DIR / "snapshots"
    snapshot_dir.mkdir(exist_ok=True)
    snapshot_file = snapshot_dir / f"joix_{joix_data.get('id')}.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(joix_data, f, indent=2, ensure_ascii=False)
        
    return history
