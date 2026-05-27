// Application State
let activeDraft = null;
let currentSearchIndex = null; // Track index currently being edited via search
let config = {};

// DOM Elements
const elSpotifyStatus = document.getElementById('spotify-status');
const elCfgGemini = document.getElementById('cfg-gemini');
const elCfgElevenlabs = document.getElementById('cfg-elevenlabs');
const elCfgSpotify = document.getElementById('cfg-spotify');
const elCfgGeminiTxt = document.getElementById('cfg-gemini-txt');
const elCfgElevenlabsTxt = document.getElementById('cfg-elevenlabs-txt');
const elCfgSpotifyTxt = document.getElementById('cfg-spotify-txt');

const elAuthBanner = document.getElementById('auth-banner');
const elBtnConnectSpotify = document.getElementById('btn-connect-spotify');
const elGeneratorPanel = document.getElementById('generator-panel');
const elCallbackSuccess = document.getElementById('callback-success');

const elSeedInput = document.getElementById('seed-input');
const elIssueNumInput = document.getElementById('issue-num-input');
const elBtnGenerate = document.getElementById('btn-generate');

const elActiveDraftPanel = document.getElementById('active-draft-panel');
const elDraftTitle = document.getElementById('draft-title');
const elDraftThemeLabel = document.getElementById('draft-theme-label');
const elDraftStatusBadge = document.getElementById('draft-status-badge');
const elTimelineContainer = document.getElementById('timeline-container');

const elHistoryPanel = document.getElementById('history-panel');
const elHistoryList = document.getElementById('history-list');

const elControlFooter = document.getElementById('control-footer');
const elFooterStatusTxt = document.getElementById('footer-status-txt');
const elBtnSaveDraft = document.getElementById('btn-save-draft');
const elBtnVoiceSynthesis = document.getElementById('btn-voice-synthesis');
const elBtnPublishPlaylist = document.getElementById('btn-publish-playlist');

const elSearchModal = document.getElementById('search-modal');
const elBtnCloseModal = document.getElementById('btn-close-modal');
const elSpotifySearchInput = document.getElementById('spotify-search-input');
const elSearchResults = document.getElementById('search-results');

const elLoadingOverlay = document.getElementById('loading-overlay');
const elLoadingText = document.getElementById('loading-text');

// Init application on load
window.addEventListener('DOMContentLoaded', async () => {
  // Check for callback status in URL query
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('auth') === 'success') {
    elCallbackSuccess.style.display = 'flex';
    // Clear URL query parameters
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  await loadAppStatus();
  await loadHistory();
  
  // Event listeners
  elBtnConnectSpotify.addEventListener('click', connectSpotify);
  elBtnGenerate.addEventListener('click', generateNewJoix);
  elBtnSaveDraft.addEventListener('click', saveDraft);
  elBtnVoiceSynthesis.addEventListener('click', triggerVoiceSynthesis);
  elBtnPublishPlaylist.addEventListener('click', publishPlaylist);
  
  elBtnCloseModal.addEventListener('click', closeModal);
  elSpotifySearchInput.addEventListener('input', debounce(searchSpotifyTracks, 400));
});

// Fetch backend status
async function loadAppStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    
    // Update config badges
    updateConfigBadge(elCfgGemini, elCfgGeminiTxt, data.gemini_configured, "Configured", "Key Missing");
    updateConfigBadge(elCfgElevenlabs, elCfgElevenlabsTxt, data.elevenlabs_configured, "Voice Ready", "Credentials Missing");
    updateConfigBadge(elCfgSpotify, elCfgSpotifyTxt, data.spotify_configured, "App Registered", "Credentials Missing");
    
    // Spotify Connection badge
    if (data.spotify_authenticated) {
      elSpotifyStatus.className = "status-badge connected";
      elSpotifyStatus.querySelector('.status-text').innerText = "Spotify Connected";
      
      elAuthBanner.style.display = 'none';
      elGeneratorPanel.style.display = 'block';
      elIssueNumInput.value = data.next_issue_number;
    } else {
      elSpotifyStatus.className = "status-badge disconnected";
      elSpotifyStatus.querySelector('.status-text').innerText = "Spotify Not Connected";
      
      elAuthBanner.style.display = 'block';
      elGeneratorPanel.style.display = 'none';
    }
    
    // Render draft if active
    if (data.current_joix) {
      activeDraft = data.current_joix;
      renderActiveDraft();
    } else {
      activeDraft = null;
      elActiveDraftPanel.style.display = 'none';
      elControlFooter.classList.remove('visible');
    }
    
    // Fetch RSS URL
    try {
      const rssRes = await fetch('/api/podcast-rss-url');
      const rssData = await rssRes.json();
      const elRssDisplay = document.getElementById('rss-feed-url-display');
      if (elRssDisplay && rssData.rss_url) {
        elRssDisplay.innerText = rssData.rss_url;
      }
    } catch (rssErr) {
      console.warn("Could not load RSS feed URL:", rssErr);
    }
  } catch (err) {
    console.error("Error fetching app status:", err);
  }
}

// Config badge UI update
function updateConfigBadge(element, textElement, isConfigured, yesText, noText) {
  if (isConfigured) {
    element.classList.add('active');
    textElement.innerText = yesText;
  } else {
    element.classList.remove('active');
    textElement.innerText = noText;
  }
}

// Redirect to Spotify Auth
async function connectSpotify() {
  showLoading("Redirecting to Spotify login...");
  try {
    const res = await fetch('/api/spotify/login');
    const data = await res.json();
    if (data.auth_url) {
      window.location.href = data.auth_url;
    } else {
      hideLoading();
      alert("Failed to get auth URL");
    }
  } catch (err) {
    hideLoading();
    alert("Connection error: " + err.message);
  }
}

// Generate JOIX playlist Draft
async function generateNewJoix() {
  const seed = elSeedInput.value.trim();
  const issueNum = elIssueNumInput.value.trim();
  
  if (!seed || !issueNum) {
    alert("Please enter both a Seed concept and an Issue number.");
    return;
  }
  
  showLoading(`Calling Gemini API...<br><span style="font-size:0.9rem; color:var(--text-secondary);">Structuring playlist based on: "${seed}"</span>`);
  
  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed: seed, issue_number: issueNum })
    });
    
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Server generation error");
    }
    
    const data = await res.json();
    activeDraft = data;
    renderActiveDraft();
    
    // Reset seed input
    elSeedInput.value = '';
    
  } catch (err) {
    alert("Generation failed: " + err.message);
  } finally {
    hideLoading();
  }
}

// Render active draft to DOM
function renderActiveDraft() {
  if (!activeDraft) return;
  
  elActiveDraftPanel.style.display = 'block';
  elDraftTitle.innerText = `JOIX Issue #${activeDraft.id}`;
  elDraftThemeLabel.innerText = `Theme: ${activeDraft.theme}`;
  
  // Set draft status text
  let statusText = "Draft Workspace";
  if (activeDraft.status === "audio_generated") {
    statusText = "Voice Generated - Ready to Publish";
    elDraftStatusBadge.style.color = "var(--accent-cyan)";
    elDraftStatusBadge.style.borderColor = "rgba(0, 242, 254, 0.2)";
    elDraftStatusBadge.style.background = "rgba(0, 242, 254, 0.05)";
  } else if (activeDraft.status === "published") {
    statusText = "Published";
    elDraftStatusBadge.style.color = "#00e676";
    elDraftStatusBadge.style.borderColor = "rgba(0, 230, 118, 0.2)";
    elDraftStatusBadge.style.background = "rgba(0, 230, 118, 0.05)";
  } else {
    elDraftStatusBadge.style.color = "var(--accent-purple)";
    elDraftStatusBadge.style.borderColor = "rgba(79, 172, 254, 0.2)";
    elDraftStatusBadge.style.background = "rgba(79, 172, 254, 0.05)";
  }
  elDraftStatusBadge.innerText = activeDraft.status.toUpperCase();
  
  // Rebuild the 13 nodes timeline
  elTimelineContainer.innerHTML = '';
  
  // Map our chunks and tracks in order
  // Node order: Intro (Chunk 1), Track 1, Link 1 (Chunk 2), Track 2, ... Outro (Chunk 7)
  const totalNodes = 13;
  for (let n = 1; n <= totalNodes; n++) {
    const isVoiceNode = n % 2 !== 0;
    
    if (isVoiceNode) {
      // Chunk index is (n + 1) / 2
      const chunkIdx = (n + 1) / 2;
      const chunk = activeDraft.chunks.find(c => c.index === chunkIdx);
      if (chunk) {
        elTimelineContainer.appendChild(createVoiceTimelineNode(chunk));
      }
    } else {
      // Track index is n / 2
      const trackIdx = n / 2;
      const track = activeDraft.tracks.find(t => t.index === trackIdx);
      if (track) {
        elTimelineContainer.appendChild(createTrackTimelineNode(track));
      }
    }
  }
  
  // Show/configure control footer
  elControlFooter.classList.add('visible');
  elFooterStatusTxt.innerText = `Draft JOIX #${activeDraft.id} saved locally.`;
  
  // Configure publish button visibility
  if (activeDraft.status === 'audio_generated') {
    elBtnPublishPlaylist.style.display = 'inline-flex';
    // Run automated check for episodes
    checkPodcastEpisodes(activeDraft.id);
  } else {
    elBtnPublishPlaylist.style.display = 'none';
  }
}

// Generate HTML Node for Voice transitions
function createVoiceTimelineNode(chunk) {
  const node = document.createElement('div');
  node.className = 'timeline-node voice';
  
  const audioIndicator = chunk.audio_generated ? '🟢 Audio Generated' : '⚪ Audio Pending';
  
  node.innerHTML = `
    <div class="node-badge">
      <div class="node-number">${chunk.index}</div>
      <span class="node-type-label">Voice</span>
    </div>
    <div class="node-content">
      <div class="node-header">
        <h3 class="node-title">${chunk.title}</h3>
        <span style="font-size:0.8rem; font-weight:600; color: ${chunk.audio_generated ? '#00e676' : 'var(--text-secondary)'};">${audioIndicator}</span>
      </div>
      <div class="voice-editor">
        <div class="editor-field">
          <label>ElevenLabs Speech Script</label>
          <textarea class="voice-script-input" data-index="${chunk.index}">${chunk.script_text}</textarea>
        </div>
        <div class="editor-field">
          <label>Spotify Episode Description Box</label>
          <textarea class="voice-desc-input" data-index="${chunk.index}">${chunk.spotify_description}</textarea>
        </div>
      </div>
    </div>
  `;
  
  // Bind live updates
  node.querySelector('.voice-script-input').addEventListener('input', (e) => {
    chunk.script_text = e.target.value;
    elFooterStatusTxt.innerText = "Draft has unsaved changes.";
  });
  
  node.querySelector('.voice-desc-input').addEventListener('input', (e) => {
    chunk.spotify_description = e.target.value;
    elFooterStatusTxt.innerText = "Draft has unsaved changes.";
  });
  
  return node;
}

// Generate HTML Node for Music tracks
function createTrackTimelineNode(track) {
  const node = document.createElement('div');
  node.className = 'timeline-node track';
  
  const isMatched = !!track.spotify_id;
  const albumArtHtml = track.album_art 
    ? `<img src="${track.album_art}" class="album-art" alt="Album Art">`
    : `<div class="album-art">🎵</div>`;
    
  node.innerHTML = `
    <div class="node-badge">
      <div class="node-number">${track.index}</div>
      <span class="node-type-label">Music</span>
    </div>
    <div class="node-content">
      <div class="track-info">
        ${albumArtHtml}
        <div class="track-details">
          <div class="track-name-display">${track.title}</div>
          <div class="track-artist-display">${track.artist}</div>
          <div class="track-meta-display">
            ${track.year ? `Year: ${track.year} &bull; ` : ''} 
            Status: ${isMatched ? `<span style="color:#00e676; font-weight:600;">Linked to Spotify</span>` : `<span style="color:#ff5252; font-weight:600;">Not Linked</span>`}
          </div>
        </div>
        <div class="track-actions">
          <button class="secondary btn-search-track" data-index="${track.index}">🔍 Search / Swap</button>
        </div>
      </div>
    </div>
  `;
  
  // Bind search/swap trigger
  node.querySelector('.btn-search-track').addEventListener('click', () => {
    openSearchModal(track.index, `${track.title} ${track.artist}`);
  });
  
  return node;
}

// Save active workspace draft
async function saveDraft() {
  if (!activeDraft) return;
  
  elFooterStatusTxt.innerText = "Saving draft...";
  
  try {
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(activeDraft)
    });
    
    if (res.ok) {
      elFooterStatusTxt.innerText = "Draft successfully saved locally.";
    } else {
      alert("Failed to save draft.");
    }
  } catch (err) {
    alert("Saving error: " + err.message);
  }
}

// Generate MP3s via ElevenLabs
async function triggerVoiceSynthesis() {
  if (!activeDraft) return;
  
  // Auto-save changes first
  await saveDraft();
  
  showLoading(`Calling ElevenLabs Voice Engine...<br><span style="font-size:0.9rem; color:var(--text-secondary);">Generating 7 MP3 speech files. This might take up to a minute.</span>`);
  
  try {
    const res = await fetch('/api/generate-voice', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Voice synthesis server error");
    }
    
    const data = await res.json();
    activeDraft = data;
    renderActiveDraft();
    
    alert("ElevenLabs audio files successfully generated and published!\n\nAll voice files have been saved to podcast/episodes/, the rss.xml feed was rebuilt, and all changes have been pushed to GitHub Pages.\n\nNow, wait a few minutes for Spotify to crawl and index your new episodes, then click the 'Publish Playlist' button.");
    
  } catch (err) {
    alert("Speech synthesis failed: " + err.message);
  } finally {
    hideLoading();
  }
}

// Query Spotify for podcast episodes
async function checkPodcastEpisodes(joixId) {
  elFooterStatusTxt.innerText = "Checking Spotify for published podcast episodes...";
  try {
    const res = await fetch(`/api/search-episodes?id=${joixId}`);
    const data = await res.json();
    
    if (data.count === 7) {
      elFooterStatusTxt.innerText = "Success: All 7 podcast episodes found on Spotify! Ready to publish.";
      elBtnPublishPlaylist.disabled = false;
      elBtnPublishPlaylist.className = "success";
    } else {
      elFooterStatusTxt.innerText = `Podcast upload status: Found ${data.count} of 7 episodes on Spotify.`;
      elBtnPublishPlaylist.disabled = true;
      elBtnPublishPlaylist.className = "secondary";
    }
  } catch (err) {
    console.warn("Could not check podcast episodes: ", err);
  }
}

// Publish finalized playlist on Spotify
async function publishPlaylist() {
  if (!activeDraft) return;
  
  showLoading(`Assembling Spotify Master Playlist...<br><span style="font-size:0.9rem; color:var(--text-secondary);">Archiving old master, loading 13 items...</span>`);
  
  try {
    const res = await fetch('/api/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(activeDraft)
    });
    
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Publishing server error");
    }
    
    const data = await res.json();
    
    alert(`JOIX Playlist published successfully!\n\nMaster playlist updated.\nPrevious master archived as '${data.published_joix.archived_playlist}'`);
    
    activeDraft = null;
    await loadAppStatus();
    await loadHistory();
    
  } catch (err) {
    alert("Publishing failed: " + err.message);
  } finally {
    hideLoading();
  }
}

// Fetch published history list
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    const historyList = await res.json();
    
    if (historyList && historyList.length > 0) {
      elHistoryPanel.style.display = 'block';
      elHistoryList.innerHTML = '';
      
      // Render newest first
      historyList.reverse().forEach(item => {
        const card = document.createElement('div');
        card.className = 'config-card';
        card.style.flexDirection = 'column';
        card.style.alignItems = 'flex-start';
        card.style.gap = '0.5rem';
        
        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; width:100%;">
            <strong style="color:var(--accent-purple);">Issue #${item.id}</strong>
            <span style="font-size:0.75rem; color:var(--text-muted);">${item.archived_playlist || 'Published'}</span>
          </div>
          <div style="font-size:0.9rem; font-weight:600; margin-top:0.25rem;">${item.theme}</div>
          <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:0.4rem; display:flex; flex-wrap:wrap; gap:0.25rem;">
            ${item.tracks.map(t => `<span style="background:rgba(255,255,255,0.05); padding: 0.2rem 0.4rem; border-radius:4px;">${t.title}</span>`).join('')}
          </div>
        `;
        elHistoryList.appendChild(card);
      });
    } else {
      elHistoryPanel.style.display = 'none';
    }
  } catch (err) {
    console.warn("Could not load archive history: ", err);
  }
}

// Modal handling
function openSearchModal(index, defaultQuery) {
  currentSearchIndex = index;
  elSearchModal.classList.add('active');
  elSpotifySearchInput.value = defaultQuery;
  elSpotifySearchInput.focus();
  searchSpotifyTracks();
}

function closeModal() {
  elSearchModal.classList.remove('active');
  elSearchResults.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 2rem 0;">Type query above to search Spotify...</p>';
}

async function searchSpotifyTracks() {
  const query = elSpotifySearchInput.value.trim();
  if (query.length < 2) return;
  
  elSearchResults.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 2rem 0;">Searching Spotify...</p>';
  
  try {
    const res = await fetch(`/api/search-tracks?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error("Search failed");
    
    const results = await res.json();
    
    if (results.length === 0) {
      elSearchResults.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 2rem 0;">No tracks found.</p>';
      return;
    }
    
    elSearchResults.innerHTML = '';
    results.forEach(track => {
      const artUrl = track.album_art || '';
      const artHtml = artUrl ? `<img src="${artUrl}" class="search-result-art" alt="">` : `<div class="search-result-art" style="display:flex; align-items:center; justify-content:center; font-size:1.25rem;">🎵</div>`;
      
      const item = document.createElement('div');
      item.className = 'search-result-item';
      item.innerHTML = `
        ${artHtml}
        <div class="search-result-info">
          <div class="search-result-name">${track.title}</div>
          <div class="search-result-artist">${track.artist} ${track.year ? `(${track.year})` : ''}</div>
        </div>
      `;
      
      item.addEventListener('click', () => {
        selectTrackForActiveDraft(track);
      });
      
      elSearchResults.appendChild(item);
    });
    
  } catch (err) {
    elSearchResults.innerHTML = `<p style="text-align: center; color: #ff5252; padding: 2rem 0;">Error searching Spotify: ${err.message}</p>`;
  }
}

function selectTrackForActiveDraft(spotifyTrack) {
  if (!activeDraft || currentSearchIndex === null) return;
  
  const track = activeDraft.tracks.find(t => t.index === currentSearchIndex);
  if (track) {
    track.spotify_id = spotifyTrack.spotify_id;
    track.spotify_uri = spotifyTrack.spotify_uri;
    track.title = spotifyTrack.title;
    track.artist = spotifyTrack.artist;
    track.year = spotifyTrack.year;
    track.album_art = spotifyTrack.album_art;
    
    // Save draft state on edit and re-render UI
    saveDraft();
    renderActiveDraft();
    closeModal();
  }
}

// Helpers
function showLoading(htmlText) {
  elLoadingText.innerHTML = htmlText;
  elLoadingOverlay.classList.add('active');
}

function hideLoading() {
  elLoadingOverlay.classList.remove('active');
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
