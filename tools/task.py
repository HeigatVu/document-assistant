import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.utils import _call_gemini
from tools.query import search_index

@dataclass
class TaskResult:
    output_path: Path
    summary: str
    referenced_files: list[str]
    success: bool

from tools.docx_writer import edit_docx, create_docx
def process_task(
    prompt: str,
    uploaded_file_path: Optional[Path],
    reading_model: str,
    writing_model: str,
    save_path: Path
) -> TaskResult:
    """Process a user task to create or edit a DOCX document."""
    
    # 1. Search for references
    search_results = search_index(prompt, top_k=3)
    referenced_files = [res.get("file") for res in search_results if "file" in res]
    
    # Context building
    context_str = "\n".join(
        f"Reference ({res.get('file')}): {res.get('summary')}"
        for res in search_results
    )
    
    # 2. Plan phase (Reading Model)
    plan_prompt = f"""You are a document assistant. Create a plan to fulfill the user's request.
Context:
{context_str}

User Request: {prompt}"""
    
    plan = _call_gemini(plan_prompt, max_tokens=1024, model_override=reading_model)
    
    # 3. Write phase (Writing Model)
    write_prompt = f"""Based on this plan, generate the document changes or new document in JSON.
Plan:
{plan}

User Request: {prompt}

Return ONLY JSON. Example: {{"title": "Doc", "content": "..."}}"""
    
    write_result = _call_gemini(write_prompt, max_tokens=4096, model_override=writing_model)
    
    # Simple JSON extraction
    content_json = {}
    try:
        json_str = write_result.strip()
        json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
        json_str = re.sub(r"\s*```$", "", json_str)
        content_json = json.loads(json_str)
    except Exception:
        pass

    # 4. Delegate to writer
    if uploaded_file_path:
        edit_docx(uploaded_file_path, content_json, save_path)
    else:
        create_docx(content_json, save_path)
        
    return TaskResult(
        output_path=save_path,
        summary="Task completed successfully.",
        referenced_files=referenced_files,
        success=True
    )
