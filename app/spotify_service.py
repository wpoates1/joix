import os
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from app.storage import get_config, DATA_DIR

# Define OAuth scopes needed
SCOPES = "playlist-read-private playlist-modify-private playlist-modify-public ugc-image-upload"

def get_oauth_manager():
    """Builds the Spotipy OAuth manager using configuration."""
    config = get_config()
    client_id = config.get("spotify_client_id")
    client_secret = config.get("spotify_client_secret")
    redirect_uri = config.get("spotify_redirect_uri")
    
    if not client_id or not client_secret:
        raise ValueError("Spotify client_id or client_secret not set in environment (.env)")
        
    cache_path = DATA_DIR / ".spotify_cache"
    
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPES,
        cache_path=str(cache_path),
        open_browser=False
    )

def get_spotify_client() -> Spotify:
    """Returns an authenticated Spotipy client. Throws if not authorized."""
    auth_manager = get_oauth_manager()
    token_info = auth_manager.get_cached_token()
    
    if not token_info:
        raise ValueError("Spotify User is not authenticated. Please authenticate via the Web UI.")
        
    # Spotipy automatically refreshes token if it's expired when using auth_manager
    if auth_manager.is_token_expired(token_info):
        token_info = auth_manager.refresh_access_token(token_info["refresh_token"])
        
    return Spotify(auth=token_info["access_token"])

def is_authenticated() -> bool:
    """Checks if the Spotify OAuth manager has a valid cached token."""
    try:
        auth_manager = get_oauth_manager()
        token_info = auth_manager.get_cached_token()
        if not token_info:
            return False
        return True
    except Exception:
        return False

def get_auth_url() -> str:
    """Generates the Spotify authorization URL."""
    auth_manager = get_oauth_manager()
    return auth_manager.get_authorize_url()

def handle_auth_code(code: str):
    """Processes the callback auth code to retrieve and cache the token."""
    auth_manager = get_oauth_manager()
    auth_manager.get_access_token(code)

def search_spotify_track(query: str, limit: int = 5) -> list:
    """Searches Spotify for music tracks matching the query.
    
    Returns:
        list of dict: Formatted search results (id, uri, name, artist, year, album_art)
    """
    sp = get_spotify_client()
    results = sp.search(q=query, type="track", limit=limit)
    
    formatted_tracks = []
    for item in results.get("tracks", {}).get("items", []):
        album = item.get("album", {})
        album_art = album.get("images", [{}])[0].get("url") if album.get("images") else None
        release_date = album.get("release_date", "")
        year = release_date.split("-")[0] if release_date else None
        
        formatted_tracks.append({
            "spotify_id": item.get("id"),
            "spotify_uri": item.get("uri"),
            "title": item.get("name"),
            "artist": item.get("artists", [{}])[0].get("name") if item.get("artists") else "Unknown",
            "year": int(year) if year and year.isdigit() else None,
            "album_art": album_art,
            "preview_url": item.get("preview_url")
        })
    return formatted_tracks

def search_podcast_episodes(joix_id: str) -> list:
    """Searches Spotify for podcast episodes matching the JOIX issue ID.
    
    Looks for episodes with titles containing 'Joix #joix_id.01' through 'Joix #joix_id.07'.
    
    Returns:
        list of dict: Episode items found
    """
    sp = get_spotify_client()
    
    # Episode search on Spotify Web API strictly requires a market. 
    # We retrieve the user's country code to specify the market.
    try:
        user_info = sp.current_user()
        market = user_info.get("country", "US")
    except Exception:
        market = "US"
        
    formatted_episodes = []
    # Search for each of the 7 episodes specifically to avoid limit restrictions
    # and search pollution from other podcasts
    for i in range(1, 8):
        query = f"Joix #{joix_id}.0{i}"
        try:
            results = sp.search(q=query, type="episode", limit=5, market=market)
            episodes = results.get("episodes", {}).get("items", [])
            
            for ep in episodes:
                title = ep.get("name", "")
                if f"#{joix_id}.0{i}" in title or f"#{joix_id}:{i}" in title or f"#{joix_id}.{i}" in title:
                    formatted_episodes.append({
                        "index": i,
                        "title": title,
                        "spotify_id": ep.get("id"),
                        "spotify_uri": ep.get("uri"),
                        "description": ep.get("description"),
                        "release_date": ep.get("release_date")
                    })
                    break # Found the match for this index, move to next
        except Exception as e:
            print(f"Error searching for episode index {i}: {e}")
            
    return formatted_episodes

def get_or_create_playlist(name: str) -> str:
    """Finds a user's playlist by name or creates it if it doesn't exist.
    
    Returns:
        str: Spotify Playlist URI
    """
    sp = get_spotify_client()
    user_id = sp.current_user()["id"]
    
    limit = 50
    offset = 0
    while True:
        playlists = sp.current_user_playlists(limit=limit, offset=offset)
        items = playlists.get("items", [])
        if not items:
            break
            
        for pl in items:
            if pl.get("name") == name:
                return pl.get("uri")
                
        if len(items) < limit:
            break
        offset += limit
        
    # Create if not found
    new_playlist = sp.current_user_playlist_create(
        name=name,
        public=False,
        description=f"Automated playlist: {name}"
    )
    return new_playlist.get("uri")

def determine_next_archive_number() -> int:
    """Scans user's playlists to find the highest JOIX XXX number and returns the next integer."""
    sp = get_spotify_client()
    
    limit = 50
    offset = 0
    highest_num = 0
    
    while True:
        playlists = sp.current_user_playlists(limit=limit, offset=offset)
        items = playlists.get("items", [])
        if not items:
            break
            
        for pl in items:
            name = pl.get("name", "")
            if name.startswith("JOIX "):
                num_part = name.replace("JOIX ", "").strip()
                if num_part.isdigit():
                    highest_num = max(highest_num, int(num_part))
                    
        if len(items) < limit:
            break
        offset += limit
        
    return highest_num + 1

def upload_playlist_cover(playlist_id: str):
    """Loads, compresses, and uploads podcast/cover.jpg to Spotify as the playlist cover."""
    sp = get_spotify_client()
    cover_path = DATA_DIR.parent / "podcast" / "cover.jpg"
    
    if not cover_path.exists():
        print(f"Playlist cover image not found at: {cover_path}")
        return
        
    try:
        from PIL import Image
        import io
        import base64
        
        img = Image.open(cover_path)
        img = img.convert("RGB")
        img.thumbnail((640, 640))
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        img_bytes = buffer.getvalue()
        
        # Max limit is 256KB
        if len(img_bytes) > 256 * 1024:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=65)
            img_bytes = buffer.getvalue()
            
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        sp.playlist_upload_cover_image(playlist_id, img_b64)
        print(f"Successfully uploaded cover art to playlist {playlist_id}")
    except Exception as e:
        print(f"Failed to upload cover art to playlist {playlist_id}: {e}")

def publish_joix_playlist(joix_data: dict, podcast_episodes: list) -> dict:
    """Performs the Spotify playlist archive and Master update.
    
    1. Reads existing tracks/episodes from JOIX Master playlist.
    2. Copies them to a new playlist named 'JOIX XXX' (archived sequence number).
    3. Clears JOIX Master playlist.
    4. Populates JOIX Master playlist with the new 13 items.
    """
    sp = get_spotify_client()
    config = get_config()
    master_name = config.get("playlist_master_name", "JOIX Master")
    
    # 1. Resolve master playlist URI
    master_uri = get_or_create_playlist(master_name)
    master_id = master_uri.split(":")[-1]
    
    # Get master playlist contents and description (to copy to archive)
    master_tracks = []
    master_description = ""
    try:
        master_details = sp.playlist(master_id, fields="description")
        master_description = master_details.get("description", "")
    except Exception:
        pass
        
    offset = 0
    while True:
        tracks_chunk = sp.playlist_items(master_id, limit=100, offset=offset)
        items = tracks_chunk.get("items", [])
        if not items:
            break
        for item in items:
            track = item.get("track")
            if track:
                master_tracks.append(track.get("uri"))
        if len(items) < 100:
            break
        offset += 100
        
    # 3. Create archive playlist if master wasn't empty
    archive_playlist_name = None
    if master_tracks:
        next_num = determine_next_archive_number()
        archive_name = f"JOIX {next_num:03d}"
        archive_uri = get_or_create_playlist(archive_name)
        archive_id = archive_uri.split(":")[-1]
        
        # Add tracks to archive in chunks of 100
        for i in range(0, len(master_tracks), 100):
            sp.playlist_add_items(archive_id, master_tracks[i:i+100])
            
        # Copy the previous description to the archived playlist
        if master_description:
            try:
                sp.playlist_change_details(archive_id, description=master_description)
            except Exception:
                pass
                
        # Upload cover art to the archive playlist
        upload_playlist_cover(archive_id)
        
        archive_playlist_name = archive_name
        print(f"Archived previous playlist tracks to {archive_name}")
        
    # 4. Assemble the 13 URIs for the new playlist
    # We need exactly 6 tracks and 7 episodes
    new_uris = []
    
    # Put them in order: Intro, Track 1, Link 1, Track 2, Link 2, ... Track 6, Outro
    # Chunks: index 1 is Intro, index 2-6 are transitions (Links 1-5), index 7 is Outro
    # Tracks: index 1 to 6
    
    # Helper to find episode URI by chunk index
    episodes_by_idx = {ep.get("index"): ep.get("spotify_uri") for ep in podcast_episodes if ep.get("index") is not None}
    
    tracks_by_idx = {t.get("index"): t.get("spotify_uri") for t in joix_data.get("tracks", [])}
    
    for i in range(1, 7):
        # Add voice episode (Intro or Link)
        ep_uri = episodes_by_idx.get(i)
        if not ep_uri:
            raise ValueError(f"Missing podcast episode URI for voice segment {i}")
        new_uris.append(ep_uri)
        
        # Add music track
        track_uri = tracks_by_idx.get(i)
        if not track_uri:
            raise ValueError(f"Missing Spotify URI for music track {i}")
        new_uris.append(track_uri)
        
    # Add final Outro episode (chunk index 7)
    outro_uri = episodes_by_idx.get(7)
    if not outro_uri:
        raise ValueError("Missing podcast episode URI for Outro (voice segment 7)")
    new_uris.append(outro_uri)
    
    # 5. Clear and populate Master playlist
    sp.playlist_replace_items(master_id, new_uris)
    
    # 6. Update Master description & cover art
    issue_id = joix_data.get("id")
    theme = joix_data.get("theme")
    description = f"JOIX Issue #{issue_id}: {theme}. A thematic music curation weaved with transitions."
    try:
        sp.playlist_change_details(master_id, description=description)
        print(f"Updated master playlist description: '{description}'")
    except Exception as ex:
        print(f"Failed to update playlist description: {ex}")
        
    # Upload custom cover art to Master
    upload_playlist_cover(master_id)
    
    # Update joix status
    joix_data["status"] = "published"
    joix_data["archived_playlist"] = archive_playlist_name
    joix_data["spotify_playlist_uri"] = master_uri
    
    return joix_data
