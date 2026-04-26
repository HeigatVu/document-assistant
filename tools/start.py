import subprocess
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

def main():
    print("Starting FastAPI backend...")
    backend = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "server/app.py")],
        cwd=REPO_ROOT,
        env=os.environ.copy()
    )
    
    print("Starting Next.js frontend...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=REPO_ROOT / "web",
        env=os.environ.copy()
    )
    
    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        backend.terminate()
        frontend.terminate()
        backend.wait()
        frontend.wait()
        print("Done.")

if __name__ == "__main__":
    main()
