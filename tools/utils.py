import os
import sys
import time
import hashlib
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import re

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent.resolve()
RAW_DIR = (REPO_ROOT / "raw").resolve()
PROCESSED_DIR = (REPO_ROOT / "processed").resolve()
MARKDOWN_DIR = (PROCESSED_DIR / "markdown").resolve()
SUMMARIES_DIR = (PROCESSED_DIR / "summaries").resolve()
CHUNKS_DIR = (PROCESSED_DIR / "chunks").resolve()
INDEX_FILE = (PROCESSED_DIR / "index.json").resolve()
OUTPUT_DIR = (REPO_ROOT / "output").resolve()
MANIFEST_FILE = (PROCESSED_DIR / ".ingest_manifest.json").resolve()
HISTORY_FILE = (PROCESSED_DIR / "history.json").resolve()


def call_gemini_cli(prompt: str, model_override: str | None = None) -> str:
    """Call Gemini CLI via subprocess."""
    cmd = ["gemini", "-p", prompt, "-y"]
    if model_override:
        cmd.extend(["-m", model_override])
    
    print(f"  [CLI] Running gemini-cli with model {model_override or 'default'}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Gemini CLI failed: {result.stderr}")
    return result.stdout

from tools.config import DEFAULT_LLM_MODEL

def call_gemini(prompt: str, max_tokens: int, model_override: str | None = None, file_path: Path | None = None, use_cli: bool = False) -> str:
    """Call Gemini API with prompt and optional file. Retries on rate limit or server busy. Or use CLI if requested."""
    if use_cli:
        if file_path:
            # We append the file path to the prompt for the CLI to read if needed, though CLI native vision isn't as direct
            prompt = f"Please read the file at {file_path.absolute()}\n\n" + prompt
        return call_gemini_cli(prompt, model_override)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("Error: google-genai not installed. Run: uv add google-genai")
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY not set in .env file")

    client = genai.Client(api_key=api_key)
    model_name = model_override or DEFAULT_LLM_MODEL

    for attempt in range(3):
        uploaded_file = None
        try:
            if attempt > 0:
                time.sleep(65)
            contents = []
            if file_path:
                uploaded_file = client.files.upload(file=str(file_path))
                contents.append(uploaded_file)
            contents.append(prompt)

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                ),
            )
            
            if uploaded_file:
                client.files.delete(name=uploaded_file.name)
                
            return response.text
        except Exception as e:
            if uploaded_file:
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass
            err = str(e)
            if ("429" in err or "503" in err) and attempt < 2:
                wait = 65 if "429" in err else 30
                print(f"  [{'Rate limit' if '429' in err else 'Server busy'}] Waiting {wait}s before retry {attempt+1}/2...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini API: max retries exceeded")

def load_manifest() -> dict:
    """Load the ingest manifest mapping source files to their state."""
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_manifest(manifest: dict) -> None:
    """Save the ingest manifest."""
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

def sha256(text: str) -> str:
    """Compute SHA256 hash of text."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of a binary file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:16]

def read_file(path: Path) -> str:
    """Read file content safely."""
    return path.read_text(encoding="utf-8") if path.exists() else ""

def write_file(path: Path, content: str) -> None:
    """Write file content safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def parse_json_from_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not match:
        raise ValueError("No JSON object found in response")
    return json.loads(match.group())

def log_skill_event(step: str, details: str, use_cli: bool = False):
    """Log a skill-related event for the dashboard history box."""
    if use_cli:
        print(json.dumps({
            "type": "skill_update",
            "step": step,
            "details": details
        }))

def load_skill(skill_name: str) -> str:
    """Load the content of a custom skill."""
    skill_path = REPO_ROOT / ".gemini/skills" / skill_name / "SKILL.md"
    if skill_path.exists():
        return f"\nEXPERT SKILL ({skill_name}):\n{skill_path.read_text()}\n"
    return ""
