import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from markitdown import MarkItDown

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

def ingest(path: Path | str) -> None:
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

        # Parse filename for metadata
        metadata = parse_filename(file_path.name)

        # 3. Convert to Markdown using MarkItDown locally
        # This avoids "Unsupported MIME type" errors in Gemini for .docx
        print(f"    [extracting] {rel_path}...")
        markdown_content = None
        try:
            result = md.convert(str(file_path))
            markdown_content = result.text_content
        except Exception as e:
            print(f"    [error] MarkItDown extraction failed on {file_path.name}: {e}")

        # Fallback to Gemini Vision for PDF if MarkItDown fails or returns empty content
        if not (markdown_content and markdown_content.strip()) and file_path.suffix.lower() == ".pdf":
            print(f"    [fallback] Attempting Gemini Vision extraction for {file_path.name}...")
            prompt_md = "This is a scanned document or has no text layer. Please perform OCR and extract the complete text and structure into Markdown format. Include all headings, lists, tables, and paragraphs exactly as they appear."
            try:
                markdown_content = call_gemini(prompt_md, max_tokens=8192, model_override=ingest_model, file_path=file_path, use_cli=True)
                if markdown_content and markdown_content.strip().startswith("```markdown"):
                    markdown_content = re.sub(r"^```markdown\s*", "", markdown_content.strip())
                    markdown_content = re.sub(r"\s*```$", "", markdown_content.strip())
                
                if markdown_content:
                    markdown_content = markdown_content.strip()
            except Exception as ge:
                print(f"    [error] Gemini fallback failed: {ge}")
                # Fall through to the final check below

        # Final check: skip if still empty or None
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
        prompt_summary = f"""Analyze this document and return a JSON summary.
        Document Content:
        {markdown_content[:50000]} 

        Return ONLY a JSON object with these fields:
        {{
          "file": "{file_path.name}",
          "Scope": "{metadata["Scope"]}",
          "Type": "{metadata["Type"]}",
          "Subject": "{metadata["Subject"]}",
          "hash": "{file_hash}",
          "type": "{file_path.suffix[1:].upper()}",
          "language": "Detect language",
          "keywords": ["list", "of", "keywords"],
          "summary": "One paragraph summary",
          "folder_path": "{str(file_path.parent)}",
          "ingested_at": "{datetime.now().isoformat()}"
        }}
        """
        
        try:
            # We can just send the prompt with the markdown text rather than re-uploading the file to save time/tokens.
            response_text = call_gemini(prompt_summary, max_tokens=2048, model_override=ingest_model)
            summary_data = parse_json_from_response(response_text)
            
            # Enforce metadata from filename to prevent LLM hallucination/overwrite
            summary_data["Scope"] = metadata["Scope"]
            summary_data["Type"] = metadata["Type"]
            summary_data["Subject"] = metadata["Subject"]
        except Exception as e:
            print(f"    [error] Gemini summarization failed: {e}")
            continue

        # Save summary
        summary_save_path = SUMMARIES_DIR / f"{slug}.json"
        write_file(summary_save_path, json.dumps(summary_data, indent=2))

        # Update manifest
        manifest[rel_path] = file_hash
        save_manifest(manifest)

    # 5. Rebuild Index
    rebuild_index()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/ingest.py <path>")
        sys.exit(1)
    ingest(sys.argv[1])
