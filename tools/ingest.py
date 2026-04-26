import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from markitdown import MarkItDown
from tools.utils import (
    _call_gemini,
    sha256_file,
    read_file,
    write_file,
    load_manifest,
    save_manifest,
    RAW_DIR,
    PROCESSED_DIR,
    MARKDOWN_DIR,
    SUMMARIES_DIR,
    INDEX_FILE,
)
from dotenv import load_dotenv

def safe_wiki_path(relative_path: str) -> Path:
    """Resolve a wiki-relative path and ensure it stays inside WIKI_DIR.

    Rejects absolute paths and any traversal (e.g. '../etc/passwd') that
    would escape the wiki directory. This is important because some paths
    come from LLM output (e.g. entity/concept page paths, source slugs) and
    could otherwise be abused via prompt injection in source documents to
    write arbitrary files.
    """
    rel = Path(relative_path)
    if rel.is_absolute():
        raise ValueError(f"Refusing absolute path inside wiki: {relative_path!r}")
    candidate = (WIKI_DIR / rel).resolve()
    wiki_root = WIKI_DIR.resolve()
    if candidate != wiki_root and wiki_root not in candidate.parents:
        raise ValueError(
            f"Refusing path that escapes wiki directory: {relative_path!r}"
        )
    return candidate


def safe_slug(slug: str) -> str:
    """Sanitize an LLM-provided slug to a safe single-segment filename stem."""
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("Empty or non-string slug")
    # Keep only lowercase letters, digits, dashes and underscores
    cleaned = re.sub(r"[^A-Za-z0-9_\-]", "-", slug.strip()).strip("-._")
    if not cleaned or cleaned in (".", ".."):
        raise ValueError(f"Unsafe slug: {slug!r}")
    # Cap length to avoid pathological filenames
    return cleaned[:100]



def build_wiki_context(source_content: str) -> str:
    """Build wiki context from index, overview, and topically relevant sources.
    
    Instead of pulling the 5 most recently modified pages (which are often
    unrelated to the new source), we extract wikilinks already present in the
    source content and pull those pages specifically. This keeps the context
    window focused and avoids feeding the LLM irrelevant pages.
    """
    parts = []

    # Always include index and overview
    if INDEX_FILE.exists():
        parts.append(f"## 30_wiki/index.md\n{read_file(INDEX_FILE)}")
    if OVERVIEW_FILE.exists():
        parts.append(f"## 30_wiki/overview.md\n{read_file(OVERVIEW_FILE)}")

    # Find pages explicitly linked in the source content
    linked_names = re.findall(r'\[\[([^\]]+)\]\]', source_content)

    # Also extract candidate names from the source frontmatter and headings
    # so even un-wikilinked references get matched
    heading_words = re.findall(r'^#{1,3}\s+(.+)$', source_content, re.MULTILINE)
    frontmatter_match = re.match(r'^---\n(.*?)\n---', source_content, re.DOTALL)
    frontmatter_text = frontmatter_match.group(1) if frontmatter_match else ""

    # Build a lookup of all existing wiki pages by stem
    sources_dir = WIKI_DIR / "sources"
    entities_dir = WIKI_DIR / "entities"
    concepts_dir = WIKI_DIR / "concepts"

    all_pages: dict[str, Path] = {}
    for d in [sources_dir, entities_dir, concepts_dir]:
        if d.exists():
            for p in d.rglob("*.md"):
                all_pages[p.stem.lower()] = p

    # Pull pages that are explicitly wikilinked
    relevant: list[Path] = []
    seen: set[str] = set()
    for name in linked_names:
        key = name.lower()
        if key in all_pages and key not in seen:
            seen.add(key)
            relevant.append(all_pages[key])

    # If we found fewer than 3 linked pages, fall back to heading-word matching
    # so we still get some context for sources with no wikilinks yet
    if len(relevant) < 3:
        for heading in heading_words:
            for word in heading.split():
                key = word.strip(":.,-").lower()
                if len(key) > 4 and key in all_pages and key not in seen:
                    seen.add(key)
                    relevant.append(all_pages[key])
                if len(relevant) >= 5:
                    break
            if len(relevant) >= 5:
                break

    # Cap at 5 pages to avoid blowing the context window
    for p in relevant[:5]:
        parts.append(f"## {p.relative_to(REPO_ROOT)}\n{read_file(p)}")

    return "\n\n---\n\n".join(parts)

def parse_json_from_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in response")
    return json.loads(match.group())


def update_index(new_entry: str, section: str = "Sources"):
    content = read_file(INDEX_FILE)
    if not content:
        content = "# Wiki Index\n\n## Overview\n- [Overview](overview.md) — living synthesis\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n"
    section_header = f"## {section}"
    if section_header in content:
        content = content.replace(section_header + "\n", section_header + "\n" + new_entry + "\n")
    else:
        content += f"\n{section_header}\n{new_entry}\n"
    write_file(INDEX_FILE, content)
    


def validate_ingest(changed_pages: list[str] | None = None) -> dict:
    """Validate wiki integrity after an ingest.

    Checks:
      1. Broken wikilinks in changed pages (or all pages if none specified)
      2. Pages not registered in index.md

    Returns dict with 'broken_links' and 'unindexed' lists.
    """
    existing_pages = {p.stem.lower() for p in all_wiki_pages()}
    index_content = read_file(INDEX_FILE).lower()

    # Determine which pages to scan for broken links
    if changed_pages:
        scan_paths = [WIKI_DIR / p for p in changed_pages if (WIKI_DIR / p).exists()]
    else:
        scan_paths = [p for p in WIKI_DIR.rglob("*.md")
                      if p.name not in ("index.md", "log.md", "lint-report.md")]

    # Check 1: Broken wikilinks
    broken_links = []
    for page_path in scan_paths:
        content = read_file(page_path)
        rel = str(page_path.relative_to(WIKI_DIR))
        for link in extract_wikilinks(content):
            # Normalize: strip paths, check stem only
            link_stem = Path(link).stem.lower() if '/' in link else link.lower()
            if link_stem not in existing_pages:
                broken_links.append((rel, link))

    # Check 2: Unindexed pages (only check changed pages)
    unindexed = []
    for p in (changed_pages or []):
        page_path = WIKI_DIR / p
        if page_path.exists():
            # Check if the page filename appears in index.md
            stem = page_path.stem.lower()
            if stem not in index_content and p not in ("log.md", "overview.md"):
                unindexed.append(p)

    return {"broken_links": broken_links, "unindexed": unindexed}

def build_ingest_prompt(source_content, source, wiki_context, schema, today, note_type):
    if note_type == "paper":
        type_instructions = """
            Note type: ACADEMIC PAPER
            - Separate objective claims (Key Methodology / Results) from subjective opinions (Personal Critique).
            - Prefix critique content with "User notes:" in the source page — do not treat as factual claims.
            - Extract authors as entity pages if they appear significantly.
            - Map Key Methodology items to concept pages aggressively.
            - Include Year and Source in the source page frontmatter.
            """
    elif note_type == "book":
        type_instructions = """
            Note type: BOOK (extracted via NotebookLM — grounded, low hallucination)
            - This is a structured extraction from a full book. The content is grounded on
              the actual source text, so treat claims as reliable.
            - PRESERVE the Chapter Checkpoints structure — do NOT flatten it.
            - Extract the author as an entity page.
            - Be VERY aggressive about creating concept pages from Key Concepts in each chapter.
            - Create entity pages for all people, organizations, and products mentioned.
            - Cross-Cutting Themes should become concept pages that link to multiple chapters.
            - The source page should keep the chapter-by-chapter structure for easy lookup.
            - Add [[wikilinks]] to EVERY concept, entity, and cross-reference inline.
            - If "Related Topics" or "Cross-Cutting Themes" are listed, check if they match
              existing wiki concepts and link them. If not, create new concept pages.
            """
    else:
        type_instructions = """
            Note type: PERSONAL KNOWLEDGE NOTE
            - Treat all content as the user's own synthesized understanding, not a citation.
            - Do NOT create author entity pages.
            - Be aggressive about creating concept pages — this note IS the primary source.
            - No external citation to attribute claims to.
            """
 
    prompt = f"""You are maintaining an LLM Wiki. Process this source document and integrate its knowledge into the wiki.
 
        {type_instructions}
        Schema and conventions:
        {schema}
 
        Current wiki state (index + recent pages):
        {wiki_context if wiki_context else "(wiki is empty — this is the first source)"}
 
        New source to ingest (file: {source.relative_to(REPO_ROOT) if source.is_relative_to(REPO_ROOT) else source.name}):
        === SOURCE START ===
        {source_content}
        === SOURCE END ===
 
        Today's date: {today}
 
        Return ONLY a valid JSON object with these fields (no markdown fences, no prose outside the JSON):
        {{
        "title": "Human-readable title for this source",
        "slug": "kebab-case-slug-for-filename",
        "source_page": "full markdown content for wiki/sources/<slug>.md — use the source page format from the schema. CRITICAL: Aggressively convert key people, products, concepts and projects into [[Wikilinks]] inline in the text. Omitting [[ ]] for known terms is a failure.",
        "index_entry": "- [Title](sources/slug.md) — one-line summary",
        "overview_update": "full updated content for wiki/overview.md, or null if no update needed",
        "entity_pages": [
            {{"path": "entities/EntityName.md", "content": "full markdown content"}}
        ],
        "concept_pages": [
            {{"path": "concepts/ConceptName.md", "content": "full markdown content"}}
        ],
        "contradictions": ["describe any contradiction with existing wiki content, or empty list"],
        "log_entry": "## [{today}] ingest | <title>\\n\\nAdded source. Key claims: ..."
        }}
        """
    return prompt

def detect_note_type(source_path: Path, content: str) -> str:
    path_str = str(source_path)
 
    # Path-based detection first — most reliable
    if "papers/my_notes" in path_str or "papers/pdf" in path_str:
        return "paper"
    if "my_knowledge_notes" in path_str:
        return "knowledge"
    # NEW: detect book type
    if "/books/" in path_str:
        return "book"
 
    # Fallback: inspect frontmatter fields
    frontmatter = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if frontmatter:
        fields = frontmatter.group(1)
 
        # NEW: check for book tag in frontmatter
        if re.search(r'tags:\s*\[.*book.*\]', fields):
            return "book"
 
        has_paper_fields = any(
            re.search(rf'^{field}:', fields, re.MULTILINE)
            for field in ["Title", "Authors", "Year", "Source"]
        )
        if has_paper_fields:
            return "paper"
 
    return "knowledge"

def read_source(source: Path) -> str:
    if source.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print("Error: pypdf not installed. Run: pip install pypdf")
            sys.exit(1)
        reader = PdfReader(str(source))
        return "\n\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )
    return source.read_text(encoding="utf-8")

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

    md_converter = MarkItDown()
    manifest = load_manifest()
    ingest_model = os.getenv("INGEST_MODEL", "gemini-1.5-flash")

    print(f"Ingesting {len(files_to_process)} files...")

    for file_path in files_to_process:
        # 2. Hash and check manifest
        file_hash = sha256_file(file_path)
        # Use relative path if possible, otherwise just filename
        try:
            rel_path = str(file_path.relative_to(RAW_DIR))
        except ValueError:
            rel_path = file_path.name
        
        if manifest.get(rel_path) == file_hash:
            print(f"  [skip] {rel_path} (unchanged)")
            continue

        print(f"  [process] {rel_path}...")

        # 3. Convert to Markdown
        try:
            result = md_converter.convert(str(file_path))
            markdown_content = result.text_content
        except Exception as e:
            print(f"    [error] MarkItDown failed on {file_path.name}: {e}")
            continue

        # Save markdown
        slug = file_path.stem.lower().replace(" ", "-")
        md_save_path = MARKDOWN_DIR / f"{slug}.md"
        write_file(md_save_path, markdown_content)

        # 4. Generate Summary via Gemini
        prompt = f"""Analyze this document and return a JSON summary.
        Document Content:
        {markdown_content[:20000]} 

        Return ONLY a JSON object with these fields:
        {{
          "file": "{file_path.name}",
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
            response_text = _call_gemini(prompt, max_tokens=2048, model_override=ingest_model)
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
    
def update_status(action: str, details: str):
    """Write a status file so Gemini CLI knows the current wiki state."""
    status_path = REPO_ROOT / "WIKI_STATUS.md"
    today = date.today().isoformat()
    
    index_content = read_file(INDEX_FILE)
    
    # Count pages by type
    papers = list((WIKI_DIR / "sources" / "papers").glob("*.md")) if (WIKI_DIR / "sources" / "papers").exists() else []
    notes = list((WIKI_DIR / "sources" / "notes").glob("*.md")) if (WIKI_DIR / "sources" / "notes").exists() else []
    books = list((WIKI_DIR / "sources" / "books").glob("*.md")) if (WIKI_DIR / "sources" / "books").exists() else []
    entities = list((WIKI_DIR / "entities").glob("*.md")) if (WIKI_DIR / "entities").exists() else []
    concepts = list((WIKI_DIR / "concepts").glob("*.md")) if (WIKI_DIR / "concepts").exists() else []

    content = f"""# Wiki Status
                Last updated: {today}
                Last action: {action}

                ## Stats
                - Papers: {len(papers)}
                - Knowledge notes: {len(notes)}
                - Books: {len(books)}
                - Entities: {len(entities)}
                - Concepts: {len(concepts)}

                ## Last Action Details
                {details}

                ## Suggested Next Steps
                - Run `/wiki-query` to explore what was just added
                - Run `/wiki-lint` to check for gaps or contradictions
                - Run `/wiki-graph` to rebuild the knowledge graph
                """
    status_path.write_text(content, encoding="utf-8")

    # Status file written.
    pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/ingest.py <path>")
        sys.exit(1)
    ingest(sys.argv[1])