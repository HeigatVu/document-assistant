from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.utils import call_gemini, parse_json_from_response
from tools.query import search_index
from tools.docx_writer import edit_docx, create_docx

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
    reading_model: str = "gemini-1.5-pro",
    writing_model: str = "gemini-1.5-flash",
    save_path: Path = Path("output.docx")
) -> TaskResult:
    """Process a user task to create or edit a DOCX document."""
    
    # 1. Search for references
    search_results = search_index(prompt, top_k=3)
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
    
    plan = call_gemini(plan_prompt, max_tokens=1024, model_override=reading_model)
    
    # 3. Write phase (Writing Model)
    write_prompt = f"""Based on this plan, generate the document changes or new document in JSON.
{style_guide}
Plan:
{plan}

User Request: {prompt}

Return ONLY JSON. Example: {{"title": "Doc", "content": "..."}}"""
    
    write_result = call_gemini(write_prompt, max_tokens=4096, model_override=writing_model)

    try:
        content_json = parse_json_from_response(write_result)
    except Exception as e:
        return TaskResult(
            output_path=save_path,
            summary=f"Failed to generate valid document content: {str(e)}",
            referenced_files=referenced_files,
            success=False
        )
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
