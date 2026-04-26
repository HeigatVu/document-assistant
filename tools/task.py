import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.utils import call_gemini, parse_json_from_response
from tools.query import search_index
from tools.docx_writer import clone_and_fill, create_docx
from tools.config import DEFAULT_READING_MODEL, DEFAULT_WRITING_MODEL

@dataclass
class TaskResult:
    output_path: Path
    summary: str
    referenced_files: list[str]
    success: bool


def process_task(
    prompt: str,
    uploaded_file_path: Optional[Path] = None,
    template_file_path: Optional[Path] = None, 
    reading_model: str = DEFAULT_READING_MODEL,
    writing_model: str = DEFAULT_WRITING_MODEL,
    save_path: Path = Path("output.docx"),
    type_filter: Optional[str] = None,
    use_cli: bool = False
) -> TaskResult:
    """Process a user task to create or edit a DOCX document."""
    
    # 1. Search for references
    search_results = search_index(prompt, top_k=3, type_filter=type_filter, use_cli=use_cli)
    referenced_files = [res.get("file") for res in search_results if "file" in res]
    
    style_guide = ""
    if template_file_path:
        from tools.utils import PROCESSED_DIR
        template_md_path = PROCESSED_DIR / f"{template_file_path.name}.md"
        if template_md_path.exists():
            style_guide = f"\nSTYLE & STRUCTURE REFERENCE (Follow this style):\n{template_md_path.read_text()}\n"
        else:
            style_guide = f"\nSTYLE & STRUCTURE REFERENCE: [Filename: {template_file_path.name}]\n"
    # Context building
    context_str = "\n".join(
        f"Reference ({res.get('file')}): {res.get('summary')}"
        for res in search_results
    )
    
    # 2. Plan phase (Reading Model)
    plan_prompt = f"""You are a document assistant. Create a plan to fulfill the user's request.
{style_guide}
Context:
{context_str}

User Request: {prompt}"""
    
    plan = call_gemini(plan_prompt, max_tokens=1024, model_override=reading_model, use_cli=use_cli)
    
    # 3. Write phase (Writing Model)
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    
    write_prompt = f"""Based on this plan, generate the document content or template replacements in JSON.
{style_guide}
Plan:
{plan}

User Request: {prompt}

Return ONLY JSON. Your JSON must include a "filename" field adhering to this naming convention:
YYYYMMDD_[Scope]_[Type]_[Subject]_[vX]
- Valid Scope: BK, IU, ND2, BV175, VinIF, Terumo, SVI, Common
- Valid Type: CV, PRO, CON, ETH, BUD, REQ, ADM, REP, SCH, PRE, CRF, FIG, GDL, COR

Format for NEW documents: 
{{
  "filename": "{today}_Scope_Type_Subject_v1.docx",
  "title": "Title",
  "sections": [
    {{"type": "heading", "level": 1, "text": "H1"}},
    {{"type": "paragraph", "text": "Text..."}},
    {{"type": "bullet_list", "items": ["I1", "I2"]}},
    {{"type": "table", "headers": ["C1", "C2"], "rows": [["V1", "V2"]]}}
  ]
}}

Format for TEMPLATE edits (if a template is used):
{{
  "filename": "{today}_Scope_Type_Subject_v1.docx",
  "replacements": [{{"old": "PLACEHOLDER", "new": "VALUE"}}]
}}"""
    
    content_json = None
    last_error = ""
    current_prompt = write_prompt
    
    for attempt in range(3):
        write_result = call_gemini(current_prompt, max_tokens=8192, model_override=writing_model, use_cli=use_cli)
        try:
            content_json = parse_json_from_response(write_result)
            break
        except Exception as e:
            last_error = str(e)
            current_prompt = write_prompt + f"\n\nYOUR PREVIOUS OUTPUT WAS INVALID JSON. ERROR: {last_error}\n\nFIX YOUR OUTPUT AND RETURN ONLY VALID JSON:\n{write_result}"
            
    if content_json is None:
        return TaskResult(
            output_path=save_path,
            summary=f"Failed to generate valid document content after 3 attempts. Last error: {last_error}",
            referenced_files=referenced_files,
            success=False
        )
        
    # Update save_path based on generated filename
    filename = content_json.get("filename")
    if filename:
        # Sanitize filename to prevent path traversal
        filename = Path(filename).name
        if not filename.endswith(".docx"):
            filename += ".docx"
        save_path = save_path.parent / filename

    # 4. Delegate to writer
    if uploaded_file_path:
        clone_and_fill(uploaded_file_path, content_json, save_path)
    elif template_file_path:
        clone_and_fill(template_file_path, content_json, save_path)
    else:
        create_docx(content_json, save_path)
        
    return TaskResult(
        output_path=save_path,
        summary="Task completed successfully.",
        referenced_files=referenced_files,
        success=True
    )

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tools/task.py <prompt>")
        sys.exit(1)
    
    prompt = sys.argv[1]
    print(f"Starting task: {prompt}")
    result = process_task(prompt, use_cli=True)
    print(f"Result: {result.summary}")
    if result.success:
        print(f"Output saved to: {result.output_path}")
