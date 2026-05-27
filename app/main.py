import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional

from app.storage import (
    load_current_joix,
    save_current_joix,
    load_history,
    add_to_history,
    get_config
)
from app.gemini_service import generate_joix
from app.elevenlabs_service import generate_joix_audio
import app.spotify_service as spotify_service

app = FastAPI(title="JOIX Playlist Controller")

# Mount frontend files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
FRONTEND_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def read_root():
    """Redirects the root URL to the Web UI index.html."""
    return RedirectResponse(url="/static/index.html")

# Pydantic models for API payloads
class GeneratePayload(BaseModel):
    seed: str
    issue_number: str

class TrackEdit(BaseModel):
    index: int
    title: str
    artist: str
    year: Optional[int] = None
    spotify_id: Optional[str] = None
    spotify_uri: Optional[str] = None
    album_art: Optional[str] = None

class ChunkEdit(BaseModel):
    index: int
    title: str
    script_text: str
    spotify_description: str
    audio_generated: bool
    audio_path: Optional[str] = None

class SavePayload(BaseModel):
    id: str
    theme: str
    status: str
    tracks: List[TrackEdit]
    chunks: List[ChunkEdit]

@app.get("/api/status")
def get_status():
    """Returns application status, API credentials state, and current draft."""
    config = get_config()
    spotify_auth = spotify_service.is_authenticated()
    
    current = load_current_joix()
    
    # Calculate next recommended issue number if Spotify is authenticated
    next_issue = "001"
    if spotify_auth:
        try:
            next_num = spotify_service.determine_next_archive_number()
            next_issue = f"{next_num:03d}"
        except Exception:
            pass
            
    return {
        "gemini_configured": bool(config.get("gemini_api_key")),
        "elevenlabs_configured": bool(config.get("elevenlabs_api_key") and config.get("elevenlabs_voice_id")),
        "spotify_configured": bool(config.get("spotify_client_id") and config.get("spotify_client_secret")),
        "spotify_authenticated": spotify_auth,
        "current_joix": current,
        "next_issue_number": next_issue
    }

@app.get("/api/podcast-rss-url")
def api_podcast_rss_url():
    """Returns the public RSS feed URL for the podcast hosted on GitHub Pages."""
    try:
        from app.git_service import get_github_pages_info
        base_url, _, _ = get_github_pages_info()
        return {"rss_url": f"{base_url}/podcast/rss.xml"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/spotify/login")
def spotify_login():
    """Generates the authorization URL to log the user into Spotify."""
    try:
        url = spotify_service.get_auth_url()
        return {"auth_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/callback")
def spotify_callback(code: str = None, error: str = None):
    """Callback target for Spotify OAuth flow."""
    if error:
        return HTMLResponse(content=f"<h3>Authentication error: {error}</h3>", status_code=400)
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")
    try:
        spotify_service.handle_auth_code(code)
        # Redirect back to the local dashboard
        return RedirectResponse(url="/static/index.html?auth=success")
    except Exception as e:
        return HTMLResponse(content=f"<h3>Failed to retrieve Spotify access token: {e}</h3>", status_code=500)

@app.post("/api/generate")
def api_generate_joix(payload: GeneratePayload):
    """Triggers playlist selection and transition scripting using Gemini."""
    try:
        # 1. Run LLM generator
        raw_joix = generate_joix(payload.seed, payload.issue_number)
        
        # 2. Attempt Spotify auto-matching for the 6 tracks
        spotify_auth = spotify_service.is_authenticated()
        if spotify_auth:
            print("Auto-matching tracks on Spotify...")
            for track in raw_joix.get("tracks", []):
                query = f"{track.get('title')} {track.get('artist')}"
                try:
                    search_results = spotify_service.search_spotify_track(query, limit=1)
                    if search_results:
                        match = search_results[0]
                        track["spotify_id"] = match["spotify_id"]
                        track["spotify_uri"] = match["spotify_uri"]
                        track["album_art"] = match["album_art"]
                        # Keep original parsed titles unless completely off
                except Exception as ex:
                    print(f"Failed to match track '{query}' on Spotify: {ex}")
                    
        # 3. Add default status and save
        raw_joix["status"] = "draft"
        save_current_joix(raw_joix)
        return raw_joix
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save")
def api_save_joix(payload: SavePayload):
    """Saves changes made in the dashboard to current_joix.json."""
    try:
        data = payload.dict()
        save_current_joix(data)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search-tracks")
def api_search_tracks(q: str = Query(..., min_length=1)):
    """Searches Spotify for matching music tracks."""
    if not spotify_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Spotify not authenticated")
    try:
        results = spotify_service.search_spotify_track(q, limit=10)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-voice")
def api_generate_voice():
    """Generates the 7 ElevenLabs MP3 files for the current draft."""
    current = load_current_joix()
    if not current:
        raise HTTPException(status_code=400, detail="No active JOIX draft found. Generate one first.")
    try:
        updated = generate_joix_audio(current)
        save_current_joix(updated)
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search-episodes")
def api_search_episodes(id: str):
    """Queries Spotify to check if the 7 podcast episodes have been indexed yet."""
    if not spotify_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Spotify not authenticated")
    try:
        episodes = spotify_service.search_podcast_episodes(id)
        return {"episodes": episodes, "count": len(episodes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/publish")
def api_publish_joix(payload: SavePayload):
    """Builds the final Spotify playlist (archives old, updates Master)."""
    if not spotify_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Spotify not authenticated")
        
    joix_id = payload.id
    
    # 1. Look for published podcast episodes on Spotify
    try:
        podcast_episodes = spotify_service.search_podcast_episodes(joix_id)
        if len(podcast_episodes) < 7:
            raise HTTPException(
                status_code=400, 
                detail=f"Only found {len(podcast_episodes)} of 7 required podcast episodes on Spotify. "
                       f"Please ensure all 7 are published and searchable before publishing."
            )
            
        # 2. Update and build playlists
        joix_data = payload.dict()
        published_joix = spotify_service.publish_joix_playlist(joix_data, podcast_episodes)
        
        # 3. Add to history, clear current draft
        add_to_history(published_joix)
        save_current_joix(None) # clear active draft
        
        return {"status": "success", "published_joix": published_joix}
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
def api_get_history():
    """Returns the list of previously published JOIX playlists."""
    try:
        return load_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# HTML response helper for oauth callback errors
from fastapi.responses import HTMLResponse
