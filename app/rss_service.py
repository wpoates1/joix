import os
import time
import email.utils
from pathlib import Path
from xml.sax.saxutils import escape
from app.storage import load_history, load_current_joix, BASE_DIR
from app.git_service import get_github_pages_info

PODCAST_DIR = BASE_DIR / "podcast"
EPISODES_DIR = PODCAST_DIR / "episodes"

PODCAST_DIR.mkdir(exist_ok=True)
EPISODES_DIR.mkdir(exist_ok=True)

def generate_podcast_rss():
    """Generates the podcast rss.xml file by reading from current draft and history JSON databases."""
    base_url, _, _ = get_github_pages_info()
    
    # Load all items from history and the active draft (if audio is generated)
    joix_items = []
    
    # Active draft check
    active = load_current_joix()
    if active and active.get("status") in ["audio_generated", "published"]:
        joix_items.append(active)
        
    # Load history
    history = load_history()
    for item in history:
        # Check if already added (in case draft status changed)
        if not any(x.get("id") == item.get("id") for x in joix_items):
            joix_items.append(item)
            
    # Sort JOIX issues chronologically (newest first, or oldest first? Podcast feeds usually show newest first)
    joix_items.sort(key=lambda x: x.get("id"), reverse=True)
    
    rss_items = []
    
    # Build RSS XML elements for each chunk
    for joix in joix_items:
        joix_id = joix.get("id")
        chunks = joix.get("chunks", [])
        
        # We want to sort chunks so they appear in correct order.
        # However, since podcast feeds are newest-first, if we want Issue 002 to be played Intro -> Outro, 
        # but Issue 002 to be above Issue 001, we should order chunks within an issue from Outro (7) down to Intro (1) 
        # so that when sorted newest-first globally, the Intro is the first one played when listening in order, or vice-versa.
        # Actually, let's order chunks 7 down to 1 so they read correctly in standard feed order.
        sorted_chunks = sorted(chunks, key=lambda x: x.get("index"), reverse=True)
        
        for chunk in sorted_chunks:
            idx = chunk.get("index")
            title = chunk.get("title")
            desc = chunk.get("spotify_description", "")
            script_text = chunk.get("script_text", "")
            
            clean_title = title.lower().replace(" ", "_").replace(":", "").replace("#", "")
            filename = f"chunk_{idx}_{clean_title}.mp3"
            
            audio_file_path = EPISODES_DIR / f"joix_{joix_id}" / filename
            
            if not audio_file_path.exists():
                print(f"Warning: Audio file {audio_file_path} not found. Skipping from RSS.")
                continue
                
            file_size = audio_file_path.stat().st_size
            
            # Formulate public URLs
            audio_url = f"{base_url}/podcast/episodes/joix_{joix_id}/{filename}"
            guid = audio_url
            
            # Calculate mock pubDate based on issue number and chunk index
            # This ensures stable, chronological sorting in podcast players
            try:
                base_time = time.time() - (1000 - int(joix_id)) * 86400 # Offset each issue by a day
                item_time = base_time + idx * 3600 # Offset each chunk by an hour
                pub_date = email.utils.formatdate(item_time, usegmt=True)
            except Exception:
                pub_date = email.utils.formatdate(time.time(), usegmt=True)
                
            formatted_title = f"Joix #{joix_id}.0{idx}: {title}"
            
            rss_items.append(f"""    <item>
      <title>{escape(formatted_title)}</title>
      <description>{escape(desc if desc else script_text)}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{audio_url}" length="{file_size}" type="audio/mpeg" />
      <guid isPermaLink="true">{guid}</guid>
      <itunes:author>JOIX Curator</itunes:author>
      <itunes:summary>{escape(script_text[:250])}...</itunes:summary>
    </item>""")

    # Build the final XML structure
    rss_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" 
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>JOIX Commentary Feed</title>
    <link>{base_url}/podcast/rss.xml</link>
    <language>en-us</language>
    <itunes:author>JOIX Curator</itunes:author>
    <description>Thematic serendipity music discovery transition voice bridges for JOIX playlists.</description>
    <itunes:summary>Narrative bridges linking music tracks on the JOIX show.</itunes:summary>
    <itunes:image href="{base_url}/podcast/cover.jpg" />
    <itunes:category text="Music" />
"""

    rss_footer = """  </channel>
</rss>"""

    rss_content = rss_header + "\n".join(rss_items) + "\n" + rss_footer
    
    rss_file = PODCAST_DIR / "rss.xml"
    with open(rss_file, "w", encoding="utf-8") as f:
        f.write(rss_content)
        
    print(f"Generated podcast RSS feed successfully at {rss_file}")
    return rss_file
