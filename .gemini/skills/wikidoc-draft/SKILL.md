---
name: wikidoc-draft
description: Activate with /wikidoc-draft. Draft a new document by searching the library for templates and examples, then exporting to DOCX.
---

# /wikidoc-draft

Use this skill to create new documents (proposals, letters, reports) based on existing templates and examples in the library.

## Trigger

```
/wikidoc-draft <description of the document you need>
```

Example: `/wikidoc-draft a research participation consent form for the Alzheimer study`

## Workflow

1. **Search Library**: Read `processed/index.json` to find relevant templates or example documents. Look for the `style_profile` field in the results to understand the document's formatting.
2. **Retrieve Context**: Read the markdown of selected documents from `processed/markdown/` to understand structure and content.
3. **Plan & Draft**: Decide whether to fill an existing template or create a new document from scratch. Generate the structured JSON.
4. **Apply Formatting**: If creating a new document, use the `format` object in your JSON sections to match the `style_profile` of your reference documents (e.g., matching indentation or alignment).
5. **Export to DOCX**:
   - Save JSON draft to `output/draft.json`.
   - For new documents: `uv run tools/export_docx.py output/draft.json output/<filename>.docx`
   - For template filling: `uv run tools/export_docx.py output/draft.json output/<filename>.docx --template <path_to_template>`
6. **Verify**: Confirm the file was created and report the output path.

## JSON Schemas

### New Document
```json
{
  "title": "Title",
  "sections": [
    {"type": "heading", "level": 1, "text": "Heading"},
    {
      "type": "paragraph", 
      "text": "Text...",
      "format": {
        "indent_left": 720,
        "first_line_indent": 360,
        "alignment": "JUSTIFY"
      }
    },
    {"type": "bullet_list", "items": ["Item 1", "Item 2"]},
    {"type": "table", "headers": ["H1", "H2"], "rows": [["V1", "V2"]]}
  ]
}
```

### Template Filling
```json
{
  "replacements": [
    {"old": "Literal placeholder text in template", "new": "Actual Value"},
    {"old": "MBEIU24013", "new": "MBEIU25001"}
  ]
}
```

Note: Replacements match **literal text** in the template file — not mustache `{{}}` syntax.

## Example

User: `/wikidoc-draft a research participation consent form for the Alzheimer study`

Agent:
1. Reads `processed/index.json`, finds `20260410_BV175_ETH_ICF_Template.docx`.
2. Reads `processed/markdown/20260410_bv175_eth_icf_template.md`.
3. Drafts replacements JSON, saves to `output/alzheimer_icf_draft.json`.
4. Runs `uv run tools/export_docx.py output/alzheimer_icf_draft.json output/Alzheimer_ICF.docx --template raw/01_Templates/Ethics_IRB/20260410_BV175_ETH_ICF_Template.docx`.
5. Reports: "Document created at `output/Alzheimer_ICF.docx`."
