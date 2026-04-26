import sys
from pathlib import Path
from tools.utils import RAW_DIR, sha256_file, load_manifest
from tools.ingest import ingest


def find_changed_files(force: bool = False) -> list[Path]:
    """Find files in RAW_DIR that are new or changed."""
    if not RAW_DIR.exists():
        return []
        
    manifest = load_manifest()
    changed_files = []
    
    for ext in ("*.pdf", "*.docx"):
        for path in RAW_DIR.rglob(ext):
            if force:
                changed_files.append(path)
                continue
                
            try:
                rel_path = str(path.relative_to(RAW_DIR))
            except ValueError:
                rel_path = path.name
                
            file_hash = sha256_file(path)
            if manifest.get(rel_path) != file_hash:
                changed_files.append(path)
                
    return changed_files
    
if __name__ == "__main__":
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv
    
    changed = find_changed_files(force=force)
    
    if not changed:
        print("No files to refresh.")
        sys.exit(0)
        
    print(f"Found {len(changed)} files to refresh.")
    
    if dry_run:
        for f in changed:
            try:
                rel = f.relative_to(RAW_DIR)
            except ValueError:
                rel = f.name
            print(f"  - {rel}")
        sys.exit(0)
        
    for f in changed:
        print(f"\nRefreshing {f.name}...")
        ingest(f)