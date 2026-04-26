import sys
import json
from pathlib import Path
from tools.utils import INDEX_FILE

def search_index(keyword: str, top_k: int = 5) -> list[dict]:
    """Search processed/index.json for the keyword."""
    if not INDEX_FILE.exists():
        return []
        
    try:
        index_data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
        
    query = keyword.lower()
    results = []
    
    for entry in index_data:
        score = 0
        
        # Check keywords (score of 2 for keyword match)
        keywords = entry.get("keywords", [])
        for kw in keywords:
            if query in kw.lower():
                score += 2
                
        # Check summary (score of 1 for summary match)
        summary = entry.get("summary", "").lower()
        if query in summary:
            score += 1
            
        if score > 0:
            results.append({"entry": entry, "score": score})
            
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # Return top_k entries
    return [r["entry"] for r in results[:top_k]]

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