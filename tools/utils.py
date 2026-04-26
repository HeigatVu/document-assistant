import os
import requests
import sys
import time
import hashlib
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
RAW_DIR = REPO_ROOT / "raw"
PROCESSED_DIR = REPO_ROOT / "processed"
MARKDOWN_DIR = PROCESSED_DIR / "markdown"
SUMMARIES_DIR = PROCESSED_DIR / "summaries"
INDEX_FILE = PROCESSED_DIR / "index.json"
OUTPUT_DIR = REPO_ROOT / "output"
MANIFEST_FILE = PROCESSED_DIR / ".ingest_manifest.json"


def _call_ollama(prompt: str, max_tokens: int) -> str:
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens}
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        print("Error: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)

def call_gemini_cli(prompt: str, max_tokens: int = 0) -> str:
    """Call the local gemini CLI binary in headless mode."""
    import subprocess
    import re
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt, "--include-directories", "30_wiki,20_raw"],
            capture_output=True,
            text=True,
            check=True
        )
        stdout = result.stdout.strip()
        
        # Filter out agent status/thought lines
        lines = stdout.splitlines()
        clean_lines = []
        for line in lines:
            # Skip lines that look like agent "thoughts", status messages, or interactive prompts
            l = line.strip()
            if not l:
                clean_lines.append(line)
                continue
            if re.match(r"^(I will|I'll|Error executing tool|YOLO mode is enabled|Processing|Reading|Checking|Searching|Would you like me to|Please let me know|Let me know if|Exit code)", l, re.IGNORECASE):
                continue
            clean_lines.append(line)
        
        return "\n".join(clean_lines).strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running gemini CLI: {e.stderr}")
        return f"Error: {e.stderr}"
    except FileNotFoundError:
        print("Error: gemini CLI not found in PATH")
        sys.exit(1)

def _call_gemini(prompt: str, max_tokens: int, model_override: str | None = None) -> str:
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