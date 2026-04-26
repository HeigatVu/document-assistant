---
name: wikidoc-ingest
description: Activate with /wikidoc-ingest. Process a PDF or DOCX file and add it to the searchable document library.
---

# /wikidoc-ingest

Use this skill to ingest new PDF or DOCX files into the document library. After ingestion, the file is searchable via `/wikidoc-search` and usable as a template in `/wikidoc-draft`.

## Trigger

```
/wikidoc-ingest <path_to_file_or_directory>
```

Examples:
- `/wikidoc-ingest raw/new_guideline.pdf`
- `/wikidoc-ingest raw/01_Templates/Admin_Support/` (ingests all files in directory)

## Workflow

1. **Run Ingestion**: Execute the ingestion tool with the provided path:
   `uv run tools/ingest.py <path_to_file_or_directory>`
2. **Report Results**: Inform the user of the outcome — files processed, metadata extracted (Scope, Type, Subject), and any errors.

## What Ingestion Does

- Converts PDF/DOCX to Markdown using `markitdown` (with Gemini Vision fallback for scanned PDFs)
- Parses the filename to extract `Scope`, `Type`, and `Subject` metadata
- Generates a JSON summary (keywords, language, one-paragraph summary) via the Gemini API
- Updates `processed/index.json` so the document is immediately searchable

## Example

User: `/wikidoc-ingest raw/01_Templates/Admin_Support/20250626_IU_ADM_DonXinHocBong_Template.docx`

Agent:
1. Runs `uv run tools/ingest.py raw/01_Templates/Admin_Support/20250626_IU_ADM_DonXinHocBong_Template.docx`.
2. Reports: "Ingested 1 file. Scope: IU, Type: ADM, Subject: DonXinHocBong_Template. Index updated."
