import sys
import json
from pathlib import Path

# Add project root to sys.path to allow running this script directly
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from tools.utils import INDEX_FILE, call_gemini, parse_json_from_response

def fallback_search(query: str, index_data: list, top_k: int, type_filter: str = None) -> list[dict]:
    results = []
    q_lower = query.lower()
    for entry in index_data:
        if type_filter and entry.get("Type") != type_filter:
            continue
        
        score = 0
        if q_lower in (entry.get("Scope") or "").lower(): score += 3
        if q_lower in (entry.get("Type") or "").lower(): score += 3
        if q_lower in (entry.get("Subject") or "").lower(): score += 2
        summary = entry.get("summary", "").lower()
        if q_lower in summary: score += 1
        
        if score > 0:
            results.append({"file": entry.get("file"), "summary": entry.get("summary"), "score": score})
            
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def search_index(query: str, top_k: int = 5, type_filter: str = None, use_cli: bool = False) -> list[dict]:
    """Search index.json using Whole-Index LLM Retrieval."""
    if not INDEX_FILE.exists():
        return []
    
    try:
        index_data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
        
    # Build a compact version of the index to send to the LLM
    catalog = []
    for entry in index_data:
        if type_filter and entry.get("Type") != type_filter:
            continue
            
        catalog.append({
            "file": entry.get("file"),
            "Scope": entry.get("Scope", "Unknown"),
            "Type": entry.get("Type", "Unknown"),
            "Subject": entry.get("Subject", "Unknown"),
            "summary": entry.get("summary", "")
        })
        
    if not catalog:
        return []
        
    prompt = f"""You are a smart document retrieval router.
You have access to a catalog of {len(catalog)} documents.
The user is making a request.
Your job is to find the top {top_k} most relevant templates or reference documents from the catalog.

User Request: {query}

Document Catalog:
{json.dumps(catalog, indent=2)}

Return ONLY a JSON array of up to {top_k} objects, representing your top choices, ordered by relevance.
Each object MUST have these fields:
- "file": the exact filename from the catalog
- "summary": a brief explanation of why this file is a good match
- "score": an integer from 1 to 10 rating the match

Example output:
[
  {{
    "file": "20250620_BV175_CON_ThueKhoan_MinhDuc_Signed_v1.docx",
    "summary": "This is a contract template that matches the requested scope.",
    "score": 9
  }}
]
"""
    
    try:
        # Using the fast model for routing
        response_text = call_gemini(prompt, max_tokens=1024, model_override="gemini-2.0-flash-lite-preview-02-05", use_cli=use_cli)
        results = parse_json_from_response(response_text)
        if isinstance(results, list):
            return results
        elif isinstance(results, dict) and "file" in results:
            return [results]
        else:
            return fallback_search(query, index_data, top_k, type_filter)
    except Exception as e:
        print(f"Error in LLM routing: {e}")
        # Fallback to basic keyword search if LLM fails
        return fallback_search(query, index_data, top_k, type_filter)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/query.py <keyword> [type_filter]")
        sys.exit(1)
        
    type_filter = sys.argv[2] if len(sys.argv) > 2 else None
    res = search_index(sys.argv[1], type_filter=type_filter)
    if not res:
        print("No results found.")
    else:
        for r in res:
            print(f"- {r.get('file')}")
            print(f"  Summary: {r.get('summary')}")
            print(f"  Score: {r.get('score')}")
            print()
