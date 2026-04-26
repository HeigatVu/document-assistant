# Wiki LLM Document Assistance

This project uses a **CLI-first architecture** where you (the Gemini CLI) are the primary interface for managing and generating documents. You reason once, call Python only for binary file operations.

## Core Rule

**To search the library:** Read `processed/index.json` directly using `read_file`. Do NOT run `query.py` or any external search tool — it is redundant and wastes API calls.

## Project Structure

```
wiki-llm-document-assistance/
├── .gemini/skills/         # Custom skills (draft-document, ingest-document, search-library)
├── tools/                  # Python tools (binary ops only)
│   ├── ingest.py           # PDF/DOCX → markdown + index entry
│   └── export_docx.py      # JSON → .docx (or template fill)
├── processed/
│   ├── index.json          # Searchable index of all ingested documents
│   ├── markdown/           # Markdown versions of ingested documents
│   ├── summaries/          # Per-document JSON summaries
│   └── chunks/             # Text chunks for retrieval
├── raw/
│   ├── 01_Templates/       # .docx templates by category
│   └── 02_Library_Assets/  # Source documents
└── output/                 # Generated documents go here
```

## Document Naming Convention

`YYYYMMDD_[Scope]_[Type]_[Subject]_[Status]_[vX].[ext]`

**Valid Scope values:** `BK`, `IU`, `ND2`, `BV175`, `VinIF`, `Terumo`, `SVI`, `Common`

**Valid Type values:**
| Code | Meaning |
|------|---------|
| `GDL` | Guideline / Regulation |
| `PRO` | Proposal |
| `CON` | Contract / Agreement |
| `ETH` | Ethics / IRB form |
| `BUD` | Budget |
| `REQ` | Request / Application |
| `ADM` | Administrative |
| `REP` | Report |
| `SCH` | Schedule / Timetable |
| `PRE` | Presentation |
| `CRF` | Case Report Form |
| `FIG` | Figure / Diagram |
| `COR` | Correspondence / Letter |
| `CV` | Curriculum Vitae |

## Index Schema (`processed/index.json`)

Each entry in the index has these fields:

```json
{
  "file": "20230924_VinIF_GDL_QuyDinhQuanLy_v1.pdf",
  "Scope": "VinIF",
  "Type": "GDL",
  "Subject": "QuyDinhQuanLy_v1",
  "hash": "d5f2a2c9...",
  "type": "PDF",
  "language": "Vietnamese",
  "keywords": ["keyword1", "keyword2"],
  "summary": "One paragraph summary of the document.",
  "folder_path": "raw/01_Templates/VinIF_Grant",
  "ingested_at": "2026-04-27T01:11:37"
}
```

To find documents: read `processed/index.json`, filter by `Scope`, `Type`, keywords, or summary content.
To read full content: read `processed/markdown/<filename_stem>.md`.

## Available Skills

| Command | What it does |
|---------|--------------|
| `/wikidoc-draft <request>` | Searches index, generates JSON, exports to DOCX |
| `/wikidoc-ingest <path>` | Runs `ingest.py` to add a file to the library |
| `/wikidoc-search <query>` | Reads `index.json` directly, no Python needed |

## CLI Tools

### Ingest a document
```bash
uv run tools/ingest.py raw/path/to/document.pdf
```

### Export JSON to DOCX (new document)
```bash
uv run tools/export_docx.py output/draft.json output/final.docx
```

### Fill a template (clone + replace placeholders)
```bash
uv run tools/export_docx.py replacements.json output/final.docx --template raw/01_Templates/path/to/Template.docx
```

## JSON Schemas for Export

### New Document
```json
{
  "title": "Document Title",
  "sections": [
    {"type": "heading", "level": 1, "text": "Section Heading"},
    {"type": "heading", "level": 2, "text": "Sub-heading"},
    {"type": "paragraph", "text": "Body paragraph text."},
    {"type": "bullet_list", "items": ["Item 1", "Item 2"]},
    {"type": "numbered_list", "items": ["Step 1", "Step 2"]},
    {"type": "table", "headers": ["Col A", "Col B"], "rows": [["val1", "val2"]]}
  ]
}
```

### Template Fill (preserves headers, footers, logos)
```json
{
  "replacements": [
    {"old": "Literal placeholder text in template", "new": "Replacement value"},
    {"old": "MBEIU24013", "new": "MBEIU25001"}
  ]
}
```

Note: Replacements match **literal text** in the template — not mustache `{{}}` syntax.
