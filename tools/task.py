import os
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.utils import call_gemini, parse_json_from_response, log_skill_event, load_skill
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
    
    # 0. Load Expert Skill (only in CLI mode)
    expert_skill = ""
    if use_cli:
        expert_skill = load_skill("wikidoc-draft")
        log_skill_event("SEARCHING", f"Activated 'wikidoc-draft' skill. Searching library for: {prompt}", use_cli)

    # 1. Search for references
    search_results = search_index(prompt, top_k=3, type_filter=type_filter, use_cli=use_cli)
    referenced_files = [res.get("file") for res in search_results if "file" in res]
    
    if use_cli:
        ref_names = ", ".join(referenced_files) if referenced_files else "None"
        log_skill_event("PLANNING", f"Found references: {ref_names}. Creating blueprint...", use_cli)

    style_guide = ""
    if template_file_path:
        from tools.utils import PROCESSED_DIR
        template_md_path = PROCESSED_DIR / "markdown" / f"{template_file_path.stem.lower().replace(' ', '-')}.md"
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
    plan_prompt = f"""You are an expert Document Architect. Your task is to create a detailed structural plan for a professional document.
{expert_skill}
{style_guide}
CONTEXT FROM LIBRARY:
{context_str}

USER REQUEST: {prompt}

INSTRUCTIONS:
1. Analyze the request and identify the specific document type and scope.
2. Define a clear structure (Headings, Sub-headings, Tables, Lists).
3. If a Style Reference is provided, mirror its tone and structural patterns.
4. Ensure the plan addresses all requirements in the User Request.
5. List any specific placeholders or data that need to be generated or replaced."""
    
    plan = call_gemini(plan_prompt, max_tokens=1024, model_override=reading_model, use_cli=use_cli)
    
    if use_cli:
        log_skill_event("GENERATING", f"Plan finalized. Starting document generation...", use_cli)

    # 3. Write phase (Writing Model)
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    
    write_prompt = f"""You are a Document Generator. Based on the ARCHITECTURAL PLAN below, generate the document content in a strict JSON format.
{expert_skill}
DOCUMENT PLAN:
{plan}

USER REQUEST: {prompt}

NAMING CONVENTION (MANDATORY):
Filename must follow: YYYYMMDD_[Scope]_[Type]_[Subject]_[vX].docx
- Valid Scopes: BK, IU, ND2, BV175, VinIF, Terumo, SVI, Common
- Valid Types: CV, PRO, CON, ETH, BUD, REQ, ADM, REP, SCH, PRE, CRF, FIG, GDL, COR
- Example: {today}_BV175_CON_ResearchContract_v1.docx

JSON OUTPUT SCHEMAS (MANDATORY):

For NEW Documents:
{{
  "filename": "...",
  "title": "...",
  "sections": [
    {{"type": "heading", "level": 1, "text": "..."}},
    {{"type": "paragraph", "text": "...", "format": {{"alignment": "JUSTIFY", "indent_left": 0, "first_line_indent": 360}}}},
    {{"type": "bullet_list", "items": ["...", "..."]}},
    {{"type": "table", "headers": ["...", "..."], "rows": [["...", "..."]]}}
  ]
}}

For TEMPLATE FILLING (Replacements):
{{
  "filename": "...",
  "replacements": [
    {{"old": "EXACT_TEXT_IN_TEMPLATE", "new": "REPLACEMENT_VALUE"}}
  ]
}}

STRICT RULES:
- Return ONLY the JSON object. No preamble or postscript.
- For template filling, the "old" value MUST be a literal string found in the reference document.
- Use professional, formal language (Vietnamese by default unless requested otherwise)."""
    
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
        
    if use_cli:
        log_skill_event("COMPLETED", f"Document saved successfully: {save_path.name}", use_cli)

    return TaskResult(
        output_path=save_path,
        summary="Task completed successfully.",
        referenced_files=referenced_files,
        success=True
    )

if __name__ == "__main__":
    import sys
    import argparse
    from tools.utils import RAW_DIR
    
    parser = argparse.ArgumentParser(description="Process a document task.")
    parser.add_argument("prompt", help="The user prompt/description.")
    parser.add_argument("--cli", action="store_true", help="Use Gemini CLI mode.")
    parser.add_argument("--template", help="Optional template filename in raw/ directory.")
    parser.add_argument("--type", help="Optional type filter for searching.")
    
    args = parser.parse_args()
    
    template_path = None
    if args.template:
        template_path = (RAW_DIR / args.template).resolve()

    result = process_task(
        prompt=args.prompt,
        template_file_path=template_path,
        use_cli=args.cli,
        type_filter=args.type
    )
    
    # In CLI mode, we output a final JSON object that matches history_entry in app.py
    # so the dashboard can immediately update the history list.
    if args.cli:
        history_entry = {
            "id": int(time.time() * 1000000000), # ns
            "prompt": args.prompt,
            "summary": result.summary,
            "output_file": str(result.output_path.name),
            "referenced_files": result.referenced_files,
            "success": result.success,
            "created_at": time.strftime("%Y-%m-%d %H:%M")
        }
        # Print it as a single line for the server to catch
        print(json.dumps(history_entry))
    else:
        print(f"Result: {result.summary}")
        if result.success:
            print(f"Output saved to: {result.output_path}")
