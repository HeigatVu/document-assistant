import os
import sys
import json
import re
from pathlib import Path

# Add project root to sys.path to allow running this script directly
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from datetime import datetime
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
        for ext in ("*.pdf", "*.docx"):
            files_to_process.extend(target_path.rglob(ext))

    if not files_to_process:
        print(f"No PDF or DOCX files found in {target_path}")
        return

    manifest = load_manifest()
    # Use the flash lite model as requested, or fallback to the env variable
    ingest_model = os.getenv("INGEST_MODEL", "gemini-2.0-flash-lite-preview-02-05")

    print(f"Ingesting {len(files_to_process)} files using {ingest_model}...")

    for file_path in files_to_process:
        # 2. Hash and check manifest
        file_hash = sha256_file(file_path)
        try:
            rel_path = str(file_path.relative_to(RAW_DIR))
        except ValueError:
            rel_path = file_path.name
        
        if manifest.get(rel_path) == file_hash:
            print(f"  [skip] {rel_path} (unchanged)")
            continue

        print(f"  [process] {rel_path}...")

        # Parse filename for metadata
        metadata = parse_filename(file_path.name)

        # 3. Convert to Markdown using Gemini Vision directly
        prompt_md = "Extract the complete text and structure of this document into Markdown format. Include all headings, lists, tables, and paragraphs exactly as they appear."
        try:
            markdown_content = call_gemini(prompt_md, max_tokens=8192, model_override=ingest_model, file_path=file_path)
            # Remove Markdown block wrappers if present
            if markdown_content.strip().startswith("```markdown"):
                markdown_content = re.sub(r"^```markdown\s*", "", markdown_content.strip())
                markdown_content = re.sub(r"\s*```$", "", markdown_content.strip())
            markdown_content = markdown_content.strip()
        except Exception as e:
            print(f"    [error] Gemini Markdown extraction failed on {file_path.name}: {e}")
            continue

        if not markdown_content:
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
        {markdown_content[:200000]} 

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
