import sys
import json
from pathlib import Path
from tools.utils import INDEX_FILE, CHUNKS_DIR

def search_chunks(keyword: str, top_k: int = 5) -> list[dict]:
    """Search processed/chunks/*.json for the keyword."""
    if not CHUNKS_DIR.exists():
        return []
    
    query = keyword.lower()
    chunk_results = []
    
    for chunk_file in CHUNKS_DIR.glob("*.json"):
        try:
            chunk = json.loads(chunk_file.read_text(encoding="utf-8"))
            text = chunk.get("text", "").lower()
            
            if query in text:
                # Basic scoring: 2 points for a hit
                chunk_results.append({
                    "file": chunk["file"],
                    "summary": chunk["text"][:500] + "...", # Use the chunk text itself as context
                    "score": 2
                })
        except Exception:
            continue
            
    chunk_results.sort(key=lambda x: x["score"], reverse=True)
    return chunk_results[:top_k]
    
def search_index(keyword: str, top_k: int = 5) -> list[dict]:
    """Search both index.json and chunks for the keyword."""
    # 1. Search document-level summaries (existing logic)
    results = []
    if INDEX_FILE.exists():
        try:
            index_data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            query = keyword.lower()
            for entry in index_data:
                score = 0
                keywords = entry.get("keywords", [])
                for kw in keywords:
                    if query in kw.lower(): score += 2
                summary = entry.get("summary", "").lower()
                if query in summary: score += 1
                
                if score > 0:
                    results.append({"file": entry.get("file"), "summary": entry.get("summary"), "score": score})
        except Exception:
            pass
    # 2. Search chunk-level content (new logic)
    chunk_results = search_chunks(keyword, top_k)
    
    # 3. Merge and deduplicate by file (keep highest score)
    merged = {}
    for r in results + chunk_results:
        fname = r["file"]
        if fname not in merged or r["score"] > merged[fname]["score"]:
            merged[fname] = r
            
    final_results = list(merged.values())
    final_results.sort(key=lambda x: x["score"], reverse=True)
    return final_results[:top_k]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/query.py <keyword>")
        sys.exit(1)
        
    res = search_index(sys.argv[1])
    if not res:
        print("No results found.")
    else:
        for r in res:
            print(f"- {r.get('file')} ({r.get('type')})")
            print(f"  Summary: {r.get('summary')}")
            print()