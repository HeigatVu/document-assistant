# Wiki LLM Document Assistant

An AI-powered document management and drafting system built on a **CLI-first architecture**. The Gemini CLI is the primary interface — it reads the document library directly, reasons over it, and calls Python only for binary file operations (ingestion and DOCX export). A Next.js web dashboard is available as a secondary interface.

## Key Features

- **Explicit Skill Commands** — Three `/wikidoc-*` commands give unambiguous control: ingest, search, and draft without relying on natural language matching.
- **Zero-Redundancy Search** — `/wikidoc-search` reads `processed/index.json` directly inside the LLM context; no subprocess or extra API call is needed.
- **Rich DOCX Generation** — `/wikidoc-draft` supports headings, paragraphs, bullet lists, numbered lists, and tables. Can generate new documents or clone-and-fill existing `.docx` templates (preserving headers, footers, and logos).
- **Intelligent Ingestion** — `/wikidoc-ingest` converts PDF and DOCX files into Markdown, semantic chunks, and metadata-rich JSON summaries stored in a local index.
- **Naming Convention Enforcement** — All documents follow `YYYYMMDD_[Scope]_[Type]_[Subject]_[vX].[ext]` with validated Scope and Type codes.
- **Web Dashboard** — A Next.js (React 19) frontend for browsing the library and triggering tasks via the FastAPI backend.

## Tech Stack

| Layer | Technology |
|-------|------------|
| CLI Interface | Gemini CLI + `/wikidoc-*` skills |
| Backend | Python 3.12+, FastAPI, Uvicorn |
| Frontend | Next.js (React 19), Tailwind CSS v4 |
| Document Processing | `python-docx`, `markitdown` |
| AI | Google Gemini API (`google-genai`) |
| Package Management | `uv` (Python), `npm` (Node.js) |

## Project Structure

```
wiki-llm-document-assistance/
├── .gemini/
│   └── skills/
│       ├── wikidoc-draft/      # /wikidoc-draft: search → draft JSON → export DOCX
│       ├── wikidoc-ingest/     # /wikidoc-ingest: convert file → add to library
│       └── wikidoc-search/     # /wikidoc-search: filter index.json directly
├── tools/
│   ├── ingest.py               # PDF/DOCX → markdown + index entry
│   ├── export_docx.py          # CLI: JSON → .docx (or template clone-and-fill)
│   ├── docx_writer.py          # DOCX creation and template-filling logic
│   ├── query.py                # Semantic search (used by web UI backend)
│   ├── task.py                 # Document generation orchestration (web UI backend)
│   ├── rename.py               # AI-assisted file renaming
│   ├── config.py               # Model name configuration
│   └── utils.py                # Gemini API wrapper, hashing, file helpers
├── server/
│   └── app.py                  # FastAPI REST API (secondary: web UI backend)
├── web/                        # Next.js frontend (secondary)
├── processed/
│   ├── index.json              # Searchable index of all ingested documents
│   ├── markdown/               # Markdown versions of source documents
│   ├── summaries/              # Per-document JSON summaries
│   └── chunks/                 # Text chunks
├── raw/                        # Source documents and .docx templates
├── output/                     # Generated documents
├── GEMINI.md                   # Project context loaded by Gemini CLI each session
└── main.py                     # CLI dispatcher for Python tools
```

## Setup

### Prerequisites

- Python 3.12+
- Node.js 20+ (only for the web dashboard)
- [uv](https://docs.astral.sh/uv/)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) (`npm install -g @google/gemini-cli`)
- A [Google Gemini API Key](https://aistudio.google.com/app/apikey)

### Installation

```bash
git clone <repository-url>
cd wiki-llm-document-assistance

# Configure environment
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY

# Install Python dependencies
uv sync

# Install frontend dependencies (optional — only needed for the web dashboard)
cd web && npm install
```

## Usage

### Primary: Gemini CLI

Run `gemini` from the project root. `GEMINI.md` and the three skills load automatically.

```bash
gemini
```

#### `/wikidoc-ingest` — Add a document to the library

```
/wikidoc-ingest raw/new_guideline.pdf
/wikidoc-ingest raw/01_Templates/Admin_Support/
```

Converts the file to Markdown, extracts metadata, generates a summary, and updates `processed/index.json`.

#### `/wikidoc-search` — Find documents

```
/wikidoc-search ethics consent forms BV175
/wikidoc-search Type:GDL VinIF
```

Reads `processed/index.json` directly inside the LLM context and returns ranked matches with summaries. No subprocess spawned.

#### `/wikidoc-draft` — Create a document

```
/wikidoc-draft a research participation consent form for the Alzheimer study
/wikidoc-draft an employment contract for John Doe at IU
```

The CLI searches the index for relevant templates, generates a structured JSON draft, and exports it to a `.docx` file in `output/`.

### JSON Schema for DOCX Export

**New document:**
```json
{
  "title": "Document Title",
  "sections": [
    {"type": "heading", "level": 1, "text": "Section Heading"},
    {"type": "paragraph", "text": "Body text."},
    {"type": "bullet_list", "items": ["Item 1", "Item 2"]},
    {"type": "numbered_list", "items": ["Step 1", "Step 2"]},
    {"type": "table", "headers": ["Column A", "Column B"], "rows": [["val1", "val2"]]}
  ]
}
```

**Template fill** (clones template, replaces literal placeholder text):
```json
{
  "replacements": [
    {"old": "Literal placeholder in template", "new": "Replacement value"},
    {"old": "MBEIU24013", "new": "MBEIU25001"}
  ]
}
```

### Python Tools (Direct CLI)

```bash
# Ingest a file
uv run tools/ingest.py raw/path/to/document.pdf

# Export JSON to DOCX
uv run tools/export_docx.py output/draft.json output/final.docx

# Clone a template and fill placeholders
uv run tools/export_docx.py replacements.json output/final.docx \
  --template raw/01_Templates/path/to/Template.docx
```

### Secondary: Web Dashboard

Launch both the backend and frontend with a single command:

```bash
uv run main.py start
```

*(Alternatively, `uv run main.py dev` also works.)*

- API: `http://localhost:8000`
- Dashboard: `http://localhost:3000`

## Document Naming Convention

```
YYYYMMDD_[Scope]_[Type]_[Subject]_[vX].[ext]
```

**Valid Scope:** `BK`, `IU`, `ND2`, `BV175`, `VinIF`, `Terumo`, `SVI`, `Common`

**Valid Type:**

| Code | Meaning | Code | Meaning |
|------|---------|------|---------|
| `GDL` | Guideline / Regulation | `REP` | Report |
| `PRO` | Proposal | `SCH` | Schedule |
| `CON` | Contract / Agreement | `PRE` | Presentation |
| `ETH` | Ethics / IRB form | `CRF` | Case Report Form |
| `BUD` | Budget | `FIG` | Figure / Diagram |
| `REQ` | Request / Application | `COR` | Correspondence |
| `ADM` | Administrative | `CV` | Curriculum Vitae |
