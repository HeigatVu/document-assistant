---
name: draft-document
description: Drafts a new document based on the user's project templates using the local processed index. Use when the user asks to generate, write, or draft a project document like a proposal, letter, or CV.
---

# Draft Document Skill

This skill allows you to intelligently draft a new document by searching the user's project index and using the exact templates they have saved.

## Process

1.  **Search the Index:**
    To find the right template, you must first search the index. Do this by running the local `query.py` script:
    ```bash
    uv run tools/query.py "[User's core request]"
    ```
    *(If the user specified a document type, you can optionally pass it as a second argument, e.g. `python tools/query.py "request letter" "REQ"`).*

2.  **Read the Template:**
    The search script will output the top matching file names. You must then read the markdown version of the chosen template from the `processed/markdown/` directory to use as a style and structure guide. The markdown file will be named similarly to the original file, just lowercased, spaces replaced with hyphens, and ending in `.md`.
    For example, if the top match is `20250620_BV175_CON_Template_v1.docx`, its markdown path is likely:
    `processed/markdown/20250620_bv175_con_template_v1.md`.
    Use `read_file` or `list_directory` in `processed/markdown/` if you are unsure of the exact filename.

3.  **Plan the Document:**
    Consider the user's request and the content of the template. Plan out what sections need to change and what specific information to insert.

4.  **Draft and Export the Document:**
    You must now generate the final document content. Since the user wants a real `.docx` file, you should format your content as JSON matching the `docx_writer.py` structure (e.g., `{"title": "Doc", "content": "..."}`) and then save it to a temporary file. Finally, run a short python snippet or call `tools/task.py` (if it supports CLI execution) to export it. 

    **Alternative (Using the local Python task runner):**
    If you want to use the built-in system instead of writing it manually, you can execute a python script that imports `process_task` from `tools.task`:
    ```python
    from tools.task import process_task
    result = process_task(
        prompt="[User's request]",
        use_cli=True # Forces it to use gemini-cli subprocess
    )
    print(result.output_path)
    ```
    
    Choose the execution method that works best.

## Rules
- Always use the user's exact templates as your structural baseline.
- Never write the output just as plain text in the terminal unless requested; always aim to generate a `.docx` file using the workspace's tools.
- Maintain the user's strict naming conventions if you are asked to save the document permanently.
