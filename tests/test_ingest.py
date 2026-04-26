import os
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Note: These will fail to import or run initially
from tools.ingest import parse_json_from_response, ingest

def test_parse_json_from_response_extracts_json_from_markdown():
    text = "Here is the result:\n```json\n{\"title\": \"Test\", \"summary\": \"Cool\"}\n```\nHope it helps!"
    result = parse_json_from_response(text)
    assert result == {"title": "Test", "summary": "Cool"}

@patch("tools.ingest.MarkItDown")
@patch("tools.ingest._call_gemini")
@patch("tools.ingest.save_manifest")
@patch("tools.ingest.load_manifest")
@patch("tools.ingest.sha256_file")
def test_ingest_creates_files_and_updates_index(
    mock_sha256_file,
    mock_load_manifest, 
    mock_save_manifest, 
    mock_call_gemini, 
    mock_markitdown, 
    tmp_path,
    monkeypatch
):
    # Setup mock directories
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    markdown_dir = processed_dir / "markdown"
    summaries_dir = processed_dir / "summaries"
    
    # Mock path constants in tools.ingest
    monkeypatch.setattr("tools.ingest.RAW_DIR", raw_dir)
    monkeypatch.setattr("tools.ingest.PROCESSED_DIR", processed_dir)
    monkeypatch.setattr("tools.ingest.MARKDOWN_DIR", markdown_dir)
    monkeypatch.setattr("tools.ingest.SUMMARIES_DIR", summaries_dir)
    monkeypatch.setattr("tools.ingest.INDEX_FILE", processed_dir / "index.json")

    # Create a dummy docx
    docx_file = raw_dir / "test.docx"
    docx_file.write_text("dummy content")
    
    # Setup mocks
    mock_sha256_file.return_value = "abc123"
    mock_load_manifest.return_value = {}
    
    mock_mid = MagicMock()
    mock_mid.convert.return_value.text_content = "# Test Document\nThis is a test."
    mock_markitdown.return_value = mock_mid
    
    summary_data = {
        "file": "test.docx",
        "hash": "abc123",
        "type": "DOCX",
        "language": "English",
        "keywords": ["test", "demo"],
        "summary": "This is a test summary.",
        "folder_path": str(raw_dir),
        "ingested_at": "2026-04-26T13:00:00"
    }
    mock_call_gemini.return_value = f"```json\n{json.dumps(summary_data)}\n```"
    
    # Run ingest
    ingest(raw_dir)
    
    # Verify markdown file created
    expected_md = markdown_dir / "test.md"
    assert expected_md.exists()
    assert expected_md.read_text() == "# Test Document\nThis is a test."
    
    # Verify summary JSON created
    expected_summary = summaries_dir / "test.json"
    assert expected_summary.exists()
    saved_summary = json.loads(expected_summary.read_text())
    assert saved_summary["file"] == "test.docx"
    
    # Verify index.json updated
    index_file = processed_dir / "index.json"
    assert index_file.exists()
    index_data = json.loads(index_file.read_text())
    assert len(index_data) == 1
    assert index_data[0]["file"] == "test.docx"