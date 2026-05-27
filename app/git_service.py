import subprocess
from pathlib import Path

def run_git_command(args: list, cwd: Path) -> str:
    """Runs a git command in the specified directory and returns output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: git {' '.join(args)}. Error: {e.stderr.strip()}")

def get_github_pages_info() -> tuple:
    """Parses git remote origin URL to calculate the GitHub Pages base URL.
    
    Returns:
        tuple: (base_url, username, repo_name)
    """
    base_dir = Path(__file__).parent.parent
    try:
        remote_url = run_git_command(["config", "--get", "remote.origin.url"], base_dir)
    except Exception:
        # Default fallback if remote is not set yet
        print("Warning: git remote origin is not configured. Defaulting to local fallback URL.")
        return "http://127.0.0.1:8000/static/podcast", "local", "joix-backend"

    # Normalize url (remove .git suffix, whitespace)
    url = remote_url.strip()
    if url.endswith(".git"):
        url = url[:-4]
        
    username = None
    repo = None
    
    if "github.com" in url:
        if url.startswith("git@github.com:"):
            # git@github.com:username/repo
            parts = url.replace("git@github.com:", "").split("/")
            if len(parts) >= 2:
                username = parts[0]
                repo = parts[1]
        elif url.startswith("https://"):
            # https://github.com/username/repo
            parts = url.replace("https://github.com/", "").split("/")
            if len(parts) >= 2:
                username = parts[0]
                repo = parts[1]
                
    if username and repo:
        # GitHub Pages url scheme:
        # If repo is username.github.io, it is root
        if repo.lower() == f"{username.lower()}.github.io":
            base_url = f"https://{username}.github.io"
        else:
            base_url = f"https://{username}.github.io/{repo}"
        return base_url, username, repo
        
    # Return local dev URL fallback
    return "http://127.0.0.1:8000/static/podcast", "local", "joix-backend"

def publish_to_github(commit_message: str):
    """Adds the podcast directory, commits, and pushes to remote GitHub repository."""
    base_dir = Path(__file__).parent.parent
    
    print("Staging podcast directory in git...")
    run_git_command(["add", "podcast/"], base_dir)
    
    # Check if there are changes to commit
    status = run_git_command(["status", "--porcelain", "podcast/"], base_dir)
    if not status:
        print("No new changes to commit in podcast feed.")
        return
        
    print(f"Committing changes: '{commit_message}'...")
    try:
        run_git_command(["commit", "-m", commit_message], base_dir)
    except Exception as e:
        # Ignore errors if there was nothing to commit
        if "nothing to commit" in str(e):
            pass
        else:
            raise e
            
    print("Pushing to remote GitHub repository...")
    try:
        # Get active branch name dynamically (e.g. master or main)
        branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], base_dir)
        # Push and set upstream to origin
        run_git_command(["push", "-u", "origin", branch], base_dir)
    except Exception as push_err:
        # Fallback to simple push if set-upstream fails
        print(f"Set-upstream push failed, trying generic push: {push_err}")
        run_git_command(["push"], base_dir)
    print("Successfully pushed to GitHub Pages!")
