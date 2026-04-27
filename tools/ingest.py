import os
import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime
from markitdown import MarkItDown
from collections import Counter
import docx

# Add project root to sys.path to allow running this script directly
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from tools.config import DEFAULT_INGEST_MODEL
from tools.utils import (
    call_gemini,
    sha256_file,
    write_file,
    load_manifest,
    save_manifest,
    parse_json_from_response,
    log_skill_event,
    load_skill,
    RAW_DIR,
    PROCESSED_DIR,
    MARKDOWN_DIR,
    SUMMARIES_DIR,
    CHUNKS_DIR,
    INDEX_FILE,
)

def rebuild_index() -> None:
    """Rebuild processed/index.json from all individual summary files."""
    index = []
    if SUMMARIES_DIR.exists():
        for summary_file in SUMMARIES_DIR.glob("*.json"):
            try:
                data = json.loads(summary_file.read_text(encoding="utf-8"))
                index.append(data)
            except Exception:
                continue
    
    write_file(INDEX_FILE, json.dumps(index, indent=2))
    print(f"Index rebuilt with {len(index)} entries.")

def parse_filename(filename: str) -> dict:
    """
    Parse filename based on YYYYMMDD_[Scope]_[Type]_[Subject]_[Status]_[vX].[ext]
    or YYYYMMDD_[Scope]_[Type]_[Subject]_[vX].[ext]
    """
    stem = Path(filename).stem
    parsed = {"Scope": "Unknown", "Type": "Unknown", "Subject": stem}
    parts = stem.split("_")
    
    if len(parts) >= 4 and parts[0].isdigit() and len(parts[0]) == 8:
        parsed["Scope"] = parts[1]
        parsed["Type"] = parts[2]
        parsed["Subject"] = "_".join(parts[3:])
        
    return parsed

def extract_docx_style_profile(path: Path) -> dict:
    """
    Extract the most common paragraph formatting (indentation, alignment) 
    from a DOCX file to create a 'Style Profile'.
    """
    if path.suffix.lower() != ".docx":
        return {}
        
    try:
        doc = docx.Document(path)
        profiles = []
        
        for p in doc.paragraphs:
            if not p.text.strip():
                continue
                
            fmt = p.paragraph_format
            
            # Use a safer way to get alignment to avoid "no XML mapping" errors
            alignment = "LEFT"
            try:
                # Accessing .alignment directly can trigger the mapping error
                raw_align = fmt.alignment
                if raw_align is not None:
                    alignment = str(raw_align)
            except Exception:
                # Default to LEFT if Word uses non-standard mapping like 'start'
                alignment = "LEFT"

            profile = {
                "indent_left": fmt.left_indent.twips if fmt.left_indent else 0,
                "first_line_indent": fmt.first_line_indent.twips if fmt.first_line_indent else 0,
                "alignment": alignment
            }
            # Clean up alignment string (e.g., 'LEFT (0)' -> 'LEFT')
            if "(" in profile["alignment"]:
                profile["alignment"] = profile["alignment"].split("(")[0].strip()
            
            # Normalize non-standard names
            if profile["alignment"] in ("START", "DISTRIBUTE"):
                profile["alignment"] = "LEFT"
            elif profile["alignment"] == "END":
                profile["alignment"] = "RIGHT"
            
            profiles.append(tuple(sorted(profile.items())))
            
        if not profiles:
            return {}
            
        # Find the most common profile (Mode)
        most_common = Counter(profiles).most_common(1)[0][0]
        return dict(most_common)
        
    except Exception as e:
        print(f"    [warning] Style extraction failed on {path.name}: {e}")
        return {}

def ingest(path: Path | str, use_cli: bool = False) -> None:
    """Ingest files from path (file or directory) into the processed library."""
    target_path = Path(path)
    if not target_path.exists():
        print(f"Error: Path not found: {target_path}")
        return

    # 1. Scan for PDF/DOCX
    files_to_process = []
    if target_path.is_file():
        if target_path.suffix.lower() in (".pdf", ".docx"):
            files_to_process.append(target_path)
    else:
        # Use a more robust case-insensitive glob
        for file_path in target_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in (".pdf", ".docx"):
                files_to_process.append(file_path)

    if not files_to_process:
        print(f"No PDF or DOCX files found in {target_path}")
        return

    manifest = load_manifest()
    ingest_model = DEFAULT_INGEST_MODEL

    expert_skill = ""
    if use_cli:
        expert_skill = load_skill("wikidoc-ingest")
        log_skill_event("INGESTING", f"Activated 'wikidoc-ingest' skill. Starting batch processing...", use_cli)

    print(f"Ingesting {len(files_to_process)} files using {ingest_model}...")

    # Initialize MarkItDown once
    md = MarkItDown()

    for file_path in files_to_process:
        # 2. Hash and check manifest
        file_hash = sha256_file(file_path)
        resolved_file = file_path.resolve()
        try:
            rel_path = str(resolved_file.relative_to(RAW_DIR))
        except ValueError:
            rel_path = file_path.name
        
        if manifest.get(rel_path) == file_hash:
            print(f"  [skip] {rel_path} (unchanged)")
            continue

        print(f"  [process] {rel_path}...")
        log_skill_event("EXTRACTING", f"Reading content from: {file_path.name}", use_cli)

        # Parse filename for metadata
        metadata = parse_filename(file_path.name)

        # 3. Convert to Markdown using MarkItDown locally
        print(f"    [extracting] {rel_path}...")
        markdown_content = None
        try:
            result = md.convert(str(file_path))
            markdown_content = result.text_content
        except Exception as e:
            print(f"    [error] MarkItDown extraction failed on {file_path.name}: {e}")

        if not (markdown_content and markdown_content.strip()) and file_path.suffix.lower() == ".pdf":
            log_skill_event("OCR", f"No text layer found. Running Vision OCR on: {file_path.name}", use_cli)
            print(f"    [fallback] Attempting Gemini Vision extraction for {file_path.name}...")
            prompt_md = f"{expert_skill}\nThis is a scanned document or has no text layer. Please perform OCR and extract the complete text and structure into Markdown format. Include all headings, lists, tables, and paragraphs exactly as they appear."
            try:
                markdown_content = call_gemini(prompt_md, max_tokens=8192, model_override=ingest_model, file_path=file_path, use_cli=True)
                if markdown_content and markdown_content.strip().startswith("```markdown"):
                    markdown_content = re.sub(r"^```markdown\s*", "", markdown_content.strip())
                    markdown_content = re.sub(r"\s*```$", "", markdown_content.strip())
                
                if markdown_content:
                    markdown_content = markdown_content.strip()
            except Exception as ge:
                print(f"    [error] Gemini fallback failed: {ge}")

        if not (markdown_content and markdown_content.strip()):
            print(f"    [error] Extracted markdown was empty for {file_path.name}")
            continue

        # Save markdown
        slug = file_path.stem.lower().replace(" ", "-")
        md_save_path = MARKDOWN_DIR / f"{slug}.md"
        write_file(md_save_path, markdown_content)
        
        print(f"    [chunking] {rel_path}...")
        paragraphs = markdown_content.split("\n\n")
        chunks = []
        current_chunk = ""
        for p in paragraphs:
            if len(current_chunk) + len(p) > 1000 and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = p
            else:
                current_chunk += "\n\n" + p if current_chunk else p
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        for i, chunk_text in enumerate(chunks):
            chunk_data = {
                "file": rel_path,
                "Scope": metadata["Scope"],
                "Type": metadata["Type"],
                "Subject": metadata["Subject"],
                "chunk_index": i,
                "total_chunks": len(chunks),
                "text": chunk_text
            }
            chunk_save_path = CHUNKS_DIR / f"{slug}_chunk_{i}.json"
            write_file(chunk_save_path, json.dumps(chunk_data, indent=2))

        # 4. Generate Summary via Gemini
        style_profile = extract_docx_style_profile(file_path)
        log_skill_event("SUMMARIZING", f"Analyzing metadata and style for: {file_path.name}", use_cli)

        # Applying 'source-driven-development' and 'security-and-hardening' philosophy
        prompt_summary = f"""{expert_skill}
        You are a Security-Conscious Librarian. Analyze the document content and generate a structured index entry.

        DOCUMENT CONTENT (Source Data):
        {markdown_content[:50000]} 

        INSTRUCTIONS:
        1. SOURCE FIDELITY: All keywords and summary points MUST be derived directly from the content. Do not hallucinate external information.
        2. PRIVACY & SECURITY (Hardening Skill): If the document contains sensitive PII (CCCD/ID numbers, exact home addresses of individuals, private phone numbers), REDACT them in the summary (e.g., use [REDACTED]).
        3. LANGUAGE: Detect the primary language of the document.
        4. STYLE: Observe the provided Style Profile and document tone.

        Return ONLY a JSON object with these fields:
        {{
        "file": "{file_path.name}",
        "Scope": "{metadata["Scope"]}",
        "Type": "{metadata["Type"]}",
        "Subject": "{metadata["Subject"]}",
        "hash": "{file_hash}",
        "type": "{file_path.suffix[1:].upper()}",
        "language": "Vietnamese/English/etc.",
        "keywords": ["keyword1", "keyword2", "..."],
        "summary": "A concise, objective summary of the document purpose and key points.",
        "style_profile": {json.dumps(style_profile)},
        "folder_path": "{str(file_path.parent)}",
        "ingested_at": "{datetime.now().isoformat()}"
        }}
        """
        
        try:
            response_text = call_gemini(prompt_summary, max_tokens=2048, model_override=ingest_model, use_cli=use_cli)
            summary_data = parse_json_from_response(response_text)
            
            summary_data["Scope"] = metadata["Scope"]
            summary_data["Type"] = metadata["Type"]
            summary_data["Subject"] = metadata["Subject"]
        except Exception as e:
            print(f"    [error] Gemini summarization failed: {e}")
            continue

        summary_save_path = SUMMARIES_DIR / f"{slug}.json"
        write_file(summary_save_path, json.dumps(summary_data, indent=2))

        manifest[rel_path] = file_hash
        save_manifest(manifest)

        # 5. Small delay to respect Rate Limits (RPM)
        print(f"    [wait] Sleeping 10s...")
        time.sleep(10)

    rebuild_index()
    log_skill_event("COMPLETED", f"Ingestion finished. Library index rebuilt.", use_cli)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/ingest.py <path> [--cli]")
        sys.exit(1)
    
    use_cli = "--cli" in sys.argv
    path = sys.argv[1] if sys.argv[1] != "--cli" else sys.argv[2]
    ingest(path, use_cli=use_cli)

