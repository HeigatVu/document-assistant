import docx
from pathlib import Path

def edit_docx(source_path: Path, changes_json: dict, output_path: Path) -> None:
    """Apply text replacements to a DOCX file and save it to output_path."""
    doc = docx.Document(source_path)
    
    replacements = changes_json.get("replacements", [])
    
    # Very basic paragraph replacement
    for p in doc.paragraphs:
        for rep in replacements:
            old_text = rep.get("old", "")
            new_text = rep.get("new", "")
            if old_text and old_text in p.text:
                p.text = p.text.replace(old_text, new_text)
                
    # Also check tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for rep in replacements:
                    old_text = rep.get("old", "")
                    new_text = rep.get("new", "")
                    if old_text and old_text in cell.text:
                        cell.text = cell.text.replace(old_text, new_text)
                        
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
