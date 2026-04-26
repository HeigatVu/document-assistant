import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
load_dotenv(REPO_ROOT / ".env")

TOOL_MAP = {
    "ingest":  "tools/ingest.py",
    "query":   "tools/query.py",
    "refresh": "tools/refresh.py",
    "serve":   "server/app.py",
    "task":    "tools/task.py",
    "export":  "tools/export_docx.py",
}

def main():
    if len(sys.argv) < 2:
        print("Wiki LLM Document Assistance")
        print("\nPrimary Usage (Gemini CLI):")
        print("  Use the interactive Gemini CLI to search, draft, and manage documents.")
        print("\nDirect Tool Usage:")
        print("  uv run main.py serve      - Launch FastAPI backend (Web UI support)")
        print("  uv run main.py ingest     - Process documents in raw directory")
        print("  uv run main.py export     - Export JSON to DOCX")
        print("  uv run main.py query      - Search the document index")
        print("  uv run main.py refresh    - Rebuild the index")
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command not in TOOL_MAP:
        print(f"Unknown command: {command}")
        print("Commands:", ", ".join(TOOL_MAP.keys()))
        sys.exit(1)

    # Inject REPO_ROOT into PYTHONPATH so 'from tools.utils' works
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    result = subprocess.run(
        [sys.executable, TOOL_MAP[command]] + rest,
        cwd=REPO_ROOT,
        env=env
    )
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()