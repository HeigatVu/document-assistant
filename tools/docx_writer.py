import docx
from pathlib import Path

def edit_docx(source_path: Path, changes_json: dict, output_path: Path) -> None:
    """Apply text replacements to a DOCX file and save it to output_path."""
    doc = docx.Document(source_path)
    
    replacements = changes_json.get("replacements", [])
    
    def replace_in_paragraph(p, old_text, new_text):
        if old_text not in p.text:
            return
            
        # Try simple run-level replacement first to preserve formatting
        replaced_in_run = False
        for run in p.runs:
            if old_text in run.text:
                run.text = run.text.replace(old_text, new_text)
                replaced_in_run = True
                
        # If the text spans multiple runs, fallback to paragraph-level replacement (loses formatting)
        if not replaced_in_run and old_text in p.text:
            p.text = p.text.replace(old_text, new_text)

    for p in doc.paragraphs:
        for rep in replacements:
            old_text = rep.get("old", "")
            new_text = rep.get("new", "")
            if old_text:
                replace_in_paragraph(p, old_text, new_text)
                
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for rep in replacements:
                        old_text = rep.get("old", "")
                        new_text = rep.get("new", "")
                        if old_text:
                            replace_in_paragraph(p, old_text, new_text)
                        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)


def create_docx(content_json: dict, output_path: Path) -> None:
    """Create a new DOCX file from structured JSON content."""
    doc = docx.Document()
    
    title = content_json.get("title", "")
    if title:
        doc.add_heading(title, 0)
        
    content = content_json.get("content", "")
    if content:
        # Split by newlines and create paragraphs
        paragraphs = content.split('\n')
        for p in paragraphs:
            if p.strip():
                doc.add_paragraph(p.strip())
                
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
