import os
import sys
import time
import hashlib
import json
from pathlib import Path
from dotenv import load_dotenv
import re

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
RAW_DIR = REPO_ROOT / "raw"
PROCESSED_DIR = REPO_ROOT / "processed"
MARKDOWN_DIR = PROCESSED_DIR / "markdown"
SUMMARIES_DIR = PROCESSED_DIR / "summaries"
CHUNKS_DIR = PROCESSED_DIR / "chunks"
INDEX_FILE = PROCESSED_DIR / "index.json"
OUTPUT_DIR = REPO_ROOT / "output"
MANIFEST_FILE = PROCESSED_DIR / ".ingest_manifest.json"
HISTORY_FILE = PROCESSED_DIR / "history.json"


def call_gemini(prompt: str, max_tokens: int, model_override: str | None = None) -> str:
    """Call Gemini API with prompt. Retries on rate limit or server busy."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("Error: google-genai not installed. Run: uv add google-genai")
        sys.exit(1)
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set in .env file")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    model_name = model_override or os.getenv("LLM_MODEL")

    for attempt in range(3):
        try:
            time.sleep(4 if attempt == 0 else 65)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text
        except Exception as e:
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
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in response")
    return json.loads(match.group())
