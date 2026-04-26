import pytest
from pathlib import Path
from unittest.mock import patch

# Note: this will fail to import initially
from tools.refresh import find_changed_files

def test_find_changed_files(tmp_path, monkeypatch):
    # Setup mock raw directory
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    
    file1 = raw_dir / "unchanged.docx"
    file1.write_text("dummy")
    
    file2 = raw_dir / "changed.pdf"
    file2.write_text("new content")
    
    file3 = raw_dir / "new.pdf"
    file3.write_text("brand new")
    
    # Mock RAW_DIR
    monkeypatch.setattr("tools.refresh.RAW_DIR", raw_dir)
    
    # Mock sha256_file to return predictable hashes based on file names
    def mock_sha(path):
        if path.name == "unchanged.docx": return "hash1"
        if path.name == "changed.pdf": return "hash2_new"
        if path.name == "new.pdf": return "hash3"
        return "hash"
        
    monkeypatch.setattr("tools.refresh.sha256_file", mock_sha)
    
    # Mock manifest
    mock_manifest = {
        "unchanged.docx": "hash1",
        "changed.pdf": "hash2_old"
        # new.pdf is not in manifest
    }
    monkeypatch.setattr("tools.refresh.load_manifest", lambda: mock_manifest)
    
    # Test standard run (should only find new and changed)
    changed = find_changed_files(force=False)
    assert len(changed) == 2
    changed_names = [p.name for p in changed]
    assert "changed.pdf" in changed_names
    assert "new.pdf" in changed_names
    assert "unchanged.docx" not in changed_names
    
    # Test force run (should return everything)
    all_files = find_changed_files(force=True)
    assert len(all_files) == 3
