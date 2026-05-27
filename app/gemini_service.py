import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.storage import get_config

# Define the Pydantic schema for structured Gemini output
class TrackItem(BaseModel):
    index: int = Field(description="1 to 6 sequence index")
    title: str = Field(description="Song title")
    artist: str = Field(description="Artist/Band name")
    year: Optional[int] = Field(description="Release year of the track, if known", default=None)

class ChunkItem(BaseModel):
    index: int = Field(description="1 to 7 sequence index")
    title: str = Field(description="Title of this podcast voice segment (e.g., 'Intro', 'Link 1', ..., 'Outro')")
    script_text: str = Field(description="ElevenLabs speech script with em-dashes and phonetic quotes as outlined in persona rules")
    spotify_description: str = Field(description="Spotify 4000-character-safe episode description box text matching the template format")

class JoixPlaylistStructure(BaseModel):
    id: str = Field(description="The playlist/issue sequential number, formatted as 3 digits (e.g. 001, 012)")
    theme: str = Field(description="The original seed idea or theme of this playlist")
    tracks: List[TrackItem] = Field(description="Exactly 6 tracks in order")
    chunks: List[ChunkItem] = Field(description="Exactly 7 voice chunks in order (Intro, 5 Transitions, Outro)")

def load_prompt_rules() -> str:
    """Reads the heart_of_joix.md rules file dynamically from the workspace root."""
    base_dir = Path(__file__).parent.parent
    prompt_file = base_dir / "heart_of_joix.md"
    
    if not prompt_file.exists():
        # Fallback default rules if file is deleted/missing
        return "You are the core intelligence backend for JOIX. Create a themed playlist of 6 tracks and 7 transitions."
        
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()

def generate_joix(seed_prompt: str, issue_number: str) -> dict:
    """Queries Gemini to generate the playlist structure based on heart_of_joix rules and a seed prompt.
    
    Args:
        seed_prompt: The starting concept, theme, or seed track.
        issue_number: The sequential number for this playlist (e.g., '012').
        
    Returns:
        dict: The structured playlist JSON representation.
    """
    config = get_config()
    api_key = config.get("gemini_api_key")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in the environment (.env file)")
        
    client = genai.Client(api_key=api_key)
    
    # Load rules dynamically from file
    prompt_rules = load_prompt_rules()
    
    system_instruction = f"""
{prompt_rules}

---

## Instructions for this Run:
You are generating Issue #{issue_number}.
The seed idea or starting point provided by the user is: "{seed_prompt}"

Return your entire response adhering strictly to the JoixPlaylistStructure schema. 
Ensure you generate exactly 6 tracks and exactly 7 voice chunks (Chunk 1 is Intro, Chunks 2-6 are Transitions, Chunk 7 is Outro).
Write the ElevenLabs script texts and Spotify Descriptions following your Persona & Output Schema guidelines exactly.
For the issue number in the templates, use "{issue_number}".
For the sequence numbers in the template headers, use the chunk index (e.g., for Chunk 1: "Joix #{issue_number}.01", Chunk 2: "Joix #{issue_number}.02").
"""

    user_message = f"Generate JOIX Issue #{issue_number} based on the seed: '{seed_prompt}'"
    
    # Use gemini-2.5-flash as it has generous free tier limits and supports Structured Outputs
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=JoixPlaylistStructure,
            temperature=0.7,
        )
    )
    
    # The SDK parses json strings directly when a schema is provided, 
    # but to get a raw dictionary we can do json.loads or load from the response text
    import json
    try:
        return json.loads(response.text)
    except Exception as e:
        # Fallback/retry/logging
        raise RuntimeError(f"Failed to parse Gemini response: {e}. Raw response: {response.text}")
