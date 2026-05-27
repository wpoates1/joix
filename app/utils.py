import re

def sanitize_filename(title: str) -> str:
    """Sanitizes filename so it contains only alphanumeric characters, underscores, and hyphens."""
    # Convert spaces to underscores, remove colons and non-alphanumeric chars
    title_lower = title.lower().replace(' ', '_').replace(':', '')
    return re.sub(r'[^a-z0-9_-]', '', title_lower)
