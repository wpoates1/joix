import os
from pathlib import Path
from xml.sax.saxutils import escape
from app.storage import load_history, load_current_joix, BASE_DIR
from app.git_service import get_github_pages_info

PODCAST_DIR = BASE_DIR / "podcast"
PODCAST_DIR.mkdir(exist_ok=True)

# Shared premium CSS styles for generated public pages
CSS_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
  --bg-primary: #08090d;
  --bg-secondary: #111218;
  --accent-purple: #4facfe;
  --accent-cyan: #00f2fe;
  --accent-magenta: #f857a6;
  --text-primary: #ffffff;
  --text-secondary: #a0a5b5;
  --text-muted: #535766;
  --glass-bg: rgba(17, 18, 24, 0.75);
  --glass-border: rgba(255, 255, 255, 0.06);
  --border-radius-lg: 16px;
  --border-radius-md: 10px;
  --border-radius-sm: 6px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Outfit', sans-serif;
  background-color: var(--bg-primary);
  background-image: 
    radial-gradient(at 0% 0%, rgba(79, 172, 254, 0.08) 0px, transparent 50%),
    radial-gradient(at 100% 100%, rgba(248, 87, 166, 0.05) 0px, transparent 50%);
  background-attachment: fixed;
  color: var(--text-primary);
  min-height: 100vh;
  padding: 3rem 1.5rem;
}

.container {
  max-width: 900px;
  margin: 0 auto;
}

header {
  margin-bottom: 4rem;
  text-align: center;
}

h1 {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 800;
  font-size: 3rem;
  letter-spacing: -0.03em;
  background: linear-gradient(135deg, var(--accent-purple), var(--accent-cyan));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 1.1rem;
  font-weight: 300;
}

.glass-panel {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: var(--border-radius-lg);
  padding: 2.5rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
  margin-bottom: 2.5rem;
}

/* Timeline grid */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  margin-top: 3rem;
}

.node {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 1.5rem;
  position: relative;
}

.node::after {
  content: '';
  position: absolute;
  left: 35px;
  top: 50px;
  bottom: -40px;
  width: 2px;
  background: linear-gradient(to bottom, var(--glass-border) 60%, transparent);
}

.node:last-child::after { display: none; }

.badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 2;
}

.number {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1rem;
  background: var(--bg-secondary);
  border: 2px solid var(--glass-border);
}

.node.voice .number { border-color: var(--accent-cyan); color: var(--accent-cyan); }
.node.track .number { border-color: var(--accent-magenta); color: var(--accent-magenta); }

.type-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-top: 0.4rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.node-content {
  background: rgba(255, 255, 255, 0.01);
  border: 1px solid var(--glass-border);
  border-radius: var(--border-radius-md);
  padding: 1.5rem;
}

.node-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.2rem;
  font-weight: 700;
  margin-bottom: 1rem;
}

.script-text {
  font-size: 1rem;
  line-height: 1.6;
  color: var(--text-secondary);
  margin-bottom: 1.25rem;
  font-style: italic;
  border-left: 2px solid var(--accent-cyan);
  padding-left: 1rem;
}

audio {
  width: 100%;
  margin-top: 0.5rem;
  outline: none;
}

/* History Card Portal */
.portal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  margin-top: 2rem;
}

.portal-card {
  text-decoration: none;
  color: inherit;
  transition: all 0.2s ease;
}

.portal-card:hover {
  transform: translateY(-4px);
  border-color: var(--accent-purple);
  box-shadow: 0 10px 30px rgba(79, 172, 254, 0.1);
}

.portal-card h3 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.3rem;
  margin-bottom: 0.5rem;
}

.portal-card p {
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.nav-link {
  color: var(--accent-purple);
  text-decoration: none;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-bottom: 2rem;
}
.nav-link:hover { text-decoration: underline; }

.track-notes {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px dashed var(--glass-border);
  font-size: 0.85rem;
  color: var(--text-secondary);
}
.track-notes ul {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.track-notes li strong {
  color: var(--accent-purple);
}
"""

def generate_issue_html(joix: dict, base_url: str):
    """Generates a dedicated static HTML page for a single JOIX issue."""
    joix_id = joix.get("id")
    theme = joix.get("theme")
    chunks = joix.get("chunks", [])
    tracks = joix.get("tracks", [])
    
    # Sort chunks and tracks
    sorted_chunks = sorted(chunks, key=lambda x: x.get("index"))
    sorted_tracks = sorted(tracks, key=lambda x: x.get("index"))
    
    timeline_nodes = []
    
    # Interleave voice and tracks
    # Total 13 nodes
    for n in range(1, 14):
        is_voice = n % 2 != 0
        if is_voice:
            chunk_idx = (n + 1) // 2
            chunk = next((c for c in sorted_chunks if c.get("index") == chunk_idx), None)
            if chunk:
                idx = chunk.get("index")
                title = chunk.get("title")
                script = chunk.get("script_text")
                desc = chunk.get("spotify_description", "")
                
                # File references
                clean_title = title.lower().replace(" ", "_").replace(":", "").replace("#", "")
                audio_rel_path = f"episodes/joix_{joix_id}/chunk_{idx}_{clean_title}.mp3"
                
                # Format deep curation notes for UI if parsed from Spotify Description
                notes_html = ""
                if "DEEP CURATION NOTES" in desc:
                    try:
                        notes_section = desc.split("DEEP CURATION NOTES")[1].split("---")[0].strip()
                        notes_lines = [line.strip().replace("•", "").strip() for line in notes_section.split("\n") if line.strip()]
                        if notes_lines:
                            notes_html = '<div class="track-notes"><ul>'
                            for line in notes_lines:
                                if ":" in line:
                                    title_part, text_part = line.split(":", 1)
                                    notes_html += f'<li><strong>{escape(title_part)}:</strong> {escape(text_part)}</li>'
                                else:
                                    notes_html += f'<li>{escape(line)}</li>'
                            notes_html += '</ul></div>'
                    except Exception:
                        pass
                
                timeline_nodes.append(f"""
      <div class="node voice">
        <div class="badge">
          <div class="number">{idx}</div>
          <span class="type-label">Voice</span>
        </div>
        <div class="node-content">
          <h3 class="node-title">{escape(title)}</h3>
          <p class="script-text">"{escape(script)}"</p>
          <audio controls src="{audio_rel_path}"></audio>
          {notes_html}
        </div>
      </div>""")
        else:
            track_idx = n // 2
            track = next((t for t in sorted_tracks if t.get("index") == track_idx), None)
            if track:
                title = track.get("title")
                artist = track.get("artist")
                year = track.get("year")
                spotify_id = track.get("spotify_id")
                
                embed_html = ""
                if spotify_id:
                    # Spotify Embed Player
                    embed_html = f"""
          <iframe src="https://open.spotify.com/embed/track/{spotify_id}?utm_source=generator" 
                  width="100%" height="152" frameBorder="0" allowfullscreen="" 
                  allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                  loading="lazy" style="border-radius: var(--border-radius-sm); margin-top: 1rem;"></iframe>"""
                else:
                    embed_html = f'<p style="color:var(--text-muted); font-size:0.9rem; margin-top:1rem;">Link to Spotify track not found</p>'
                    
                timeline_nodes.append(f"""
      <div class="node track">
        <div class="badge">
          <div class="number">{track_idx}</div>
          <span class="type-label">Music</span>
        </div>
        <div class="node-content">
          <h3 class="node-title" style="margin-bottom:0.25rem;">{escape(title)}</h3>
          <p style="color:var(--text-secondary); font-size:0.95rem;">by {escape(artist)} {f'({year})' if year else ''}</p>
          {embed_html}
        </div>
      </div>""")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JOIX Issue #{joix_id} - {escape(theme.capitalize())}</title>
  <style>
    {CSS_STYLE}
  </style>
</head>
<body>
  <div class="container">
    <a href="index.html" class="nav-link">&larr; Back to Directory</a>
    
    <article class="glass-panel">
      <header style="margin-bottom: 2rem; text-align: left;">
        <span style="text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.15em; color: var(--accent-purple); font-weight: 700;">JOIX Series</span>
        <h1 style="text-align: left; font-size: 2.75rem; margin-top:0.25rem;">Issue #{joix_id}</h1>
        <p class="subtitle" style="font-size:1.25rem; font-weight: 500; color: var(--text-primary); margin-top:0.25rem;">{escape(theme.capitalize())}</p>
      </header>
      
      <div class="timeline">
        {"".join(timeline_nodes)}
      </div>
    </article>
  </div>
</body>
</html>
"""
    file_path = PODCAST_DIR / f"issue_{joix_id}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return file_path

def generate_index_html(joix_list: list, base_url: str):
    """Generates the index portal landing page listing all JOIX issues."""
    cards_html = []
    
    for joix in joix_list:
        joix_id = joix.get("id")
        theme = joix.get("theme")
        tracks = joix.get("tracks", [])
        
        tracks_text = ", ".join([f'"{t.get("title")}"' for t in sorted(tracks, key=lambda x: x.get("index"))[:3]])
        if len(tracks) > 3:
            tracks_text += ", and more..."
            
        cards_html.append(f"""
      <a href="issue_{joix_id}.html" class="glass-panel portal-card">
        <span style="text-transform: uppercase; font-size: 0.7rem; color: var(--accent-purple); font-weight: 700; letter-spacing: 0.1em;">Issue #{joix_id}</span>
        <h3>{escape(theme.capitalize())}</h3>
        <p style="margin-top:0.5rem; font-size:0.85rem; color: var(--text-muted);">Featuring tracks by {tracks_text}</p>
      </a>""")
      
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JOIX - Thematic Music Curation</title>
  <style>
    {CSS_STYLE}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>JOIX</h1>
      <p class="subtitle">Commentary, thematic serendipity, and curated pathways through sound.</p>
      <div style="margin-top: 1rem;">
        <a href="rss.xml" class="nav-link" target="_blank" style="font-size:0.9rem; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding: 0.4rem 1rem; border-radius: 30px;">📡 Podcast RSS Feed</a>
      </div>
    </header>
    
    <section>
      <h2 style="font-family: 'Space Grotesk', sans-serif; font-size: 1.5rem; margin-bottom: 1.5rem; border-bottom: 1px solid var(--glass-border); padding-bottom: 0.5rem;">Curation Directory</h2>
      <div class="portal-grid">
        {"".join(cards_html) if cards_html else '<p style="color:var(--text-secondary); text-align:center; padding: 3rem 0; width:100%;">No issues published yet.</p>'}
      </div>
    </section>
  </div>
</body>
</html>
"""
    file_path = PODCAST_DIR / "index.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return file_path

def generate_static_website():
    """Generates index portal and individual subpages for all published JOIX configurations."""
    base_url, _, _ = get_github_pages_info()
    
    # Collect all items
    joix_list = []
    active = load_current_joix()
    if active and active.get("status") in ["audio_generated", "published"]:
        joix_list.append(active)
        
    history = load_history()
    for item in history:
        if not any(x.get("id") == item.get("id") for x in joix_list):
            joix_list.append(item)
            
    # Sort chronologically
    joix_list.sort(key=lambda x: x.get("id"), reverse=True)
    
    # Generate subpages
    for joix in joix_list:
        generate_issue_html(joix, base_url)
        
    # Generate index page
    generate_index_html(joix_list, base_url)
    print("Static website generated successfully inside podcast/ folder!")
