import os
import re
import requests
from pathlib import Path
from app.storage import get_config
from app.rss_service import EPISODES_DIR, PODCAST_DIR, generate_podcast_rss
from app.git_service import publish_to_github

def sanitize_filename(title: str) -> str:
    """Sanitizes filename so it contains only alphanumeric characters, underscores, and hyphens."""
    # Convert spaces to underscores, remove colons and non-alphanumeric chars
    title_lower = title.lower().replace(' ', '_').replace(':', '')
    return re.sub(r'[^a-z0-9_-]', '', title_lower)

def generate_voice_file(text: str, filename: str, joix_id: str) -> Path:
    """Calls the ElevenLabs API to synthesize speech from text and saves it locally.
    
    Args:
        text: The script text to synthesize.
        filename: The desired name of the file (e.g. 'chunk_1_intro.mp3').
        joix_id: The ID of the JOIX playlist (e.g. '012') to group files.
        
    Returns:
        Path: The absolute path of the generated audio file.
    """
    config = get_config()
    api_key = config.get("elevenlabs_api_key")
    voice_id = config.get("elevenlabs_voice_id")
    
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is not configured in the environment (.env file)")
    if not voice_id:
        raise ValueError("ELEVENLABS_VOICE_ID is not configured in the environment (.env file)")
        
    # Setup folders inside the podcast directory (which is pushed to Git)
    joix_output_dir = EPISODES_DIR / f"joix_{joix_id}"
    joix_output_dir.mkdir(exist_ok=True)
    
    output_filepath = joix_output_dir / filename
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "accept": "audio/mpeg",
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # We use eleven_multilingual_v2 for rich tone and high fidelity
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error (Status Code: {response.status_code}): {response.text}"
        )
        
    with open(output_filepath, "wb") as f:
        f.write(response.content)
        
    return output_filepath

def generate_joix_audio(joix_data: dict) -> dict:
    """Generates all 7 voice segments, updates the RSS feed, and publishes it to GitHub.
    
    Args:
        joix_data: The dictionary structure of the JOIX playlist.
        
    Returns:
        dict: The updated JOIX playlist dictionary containing local audio paths.
    """
    joix_id = joix_data.get("id")
    chunks = joix_data.get("chunks", [])
    
    # Generate MP3 files
    for chunk in chunks:
        index = chunk.get("index")
        title = chunk.get("title")
        script = chunk.get("script_text")
        
        # Clean title for filename
        clean_title = sanitize_filename(title)
        filename = f"chunk_{index}_{clean_title}.mp3"
        
        # Generate voice
        print(f"Generating audio for chunk {index}: {title}...")
        audio_path = generate_voice_file(script, filename, joix_id)
        
        # Update chunk state
        chunk["audio_generated"] = True
        chunk["audio_path"] = str(audio_path)
        
    # Write metadata file for user upload reference
    joix_output_dir = EPISODES_DIR / f"joix_{joix_id}"
    metadata_file = joix_output_dir / "spotify_podcast_metadata.txt"
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        f.write(f"=== Spotify Podcast Episodes Metadata for JOIX #{joix_id} ===\n\n")
        for chunk in chunks:
            f.write(f"--- EPISODE CHUNK {chunk.get('index')}: {chunk.get('title')} ---\n")
            f.write(f"Audio File: chunk_{chunk.get('index')}_{sanitize_filename(chunk.get('title'))}.mp3\n")
            f.write(f"Recommended Episode Title: Joix #{joix_id}.0{chunk.get('index')}: {chunk.get('title')}\n\n")
            f.write("Episode Description:\n")
            f.write(chunk.get("spotify_description"))
            f.write("\n\n" + "="*50 + "\n\n")
            
    joix_data["status"] = "audio_generated"
    
    # 1. Regenerate local rss.xml
    print("Rebuilding RSS xml...")
    generate_podcast_rss()
    
    # 2. Push files and RSS to GitHub Pages
    try:
        print("Publishing to GitHub Pages...")
        publish_to_github(f"Publish JOIX #{joix_id} audio and update RSS feed")
    except Exception as e:
        print(f"Warning: Git push failed: {e}. (Please ensure git remote is configured and you have push access).")
        
    return joix_data
