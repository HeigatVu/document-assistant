import os
from pathlib import Path
import pytest

from tools.utils import (
    sha256,
    sha256_file,
    read_file,
    write_file,
    RAW_DIR,
    PROCESSED_DIR,
    MARKDOWN_DIR,
    SUMMARIES_DIR,
    INDEX_FILE,
    OUTPUT_DIR,
    MANIFEST_FILE,
)

def test_sha256_returns_16_char_hex():
    result = sha256("test data")
    assert len(result) == 16
    # Ensure it's valid hex
    int(result, 16)

def test_sha256_file_hashes_binary_file(tmp_path):
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"\x00\x01\x02")
    result = sha256_file(test_file)
    assert len(result) == 16
    int(result, 16)

def test_read_file_returns_empty_string_for_missing_file(tmp_path):
    missing_file = tmp_path / "missing.txt"
    assert read_file(missing_file) == ""

def test_write_file_creates_parent_dirs(tmp_path):
    nested_file = tmp_path / "deep" / "nested" / "file.txt"
    write_file(nested_file, "content")
    assert nested_file.exists()
    assert nested_file.read_text() == "content"

def test_path_constants_point_to_correct_dirs():
    assert isinstance(RAW_DIR, Path)
    assert RAW_DIR.name == "raw"
    
    assert isinstance(PROCESSED_DIR, Path)
    assert PROCESSED_DIR.name == "processed"
    
    assert isinstance(MARKDOWN_DIR, Path)
    assert MARKDOWN_DIR.parent == PROCESSED_DIR
    assert MARKDOWN_DIR.name == "markdown"
    
    assert isinstance(SUMMARIES_DIR, Path)
    assert SUMMARIES_DIR.parent == PROCESSED_DIR
    assert SUMMARIES_DIR.name == "summaries"
    
    assert isinstance(INDEX_FILE, Path)
    assert INDEX_FILE.parent == PROCESSED_DIR
    assert INDEX_FILE.name == "index.json"
    
    assert isinstance(OUTPUT_DIR, Path)
    assert OUTPUT_DIR.name == "output"
    
    assert isinstance(MANIFEST_FILE, Path)
    assert MANIFEST_FILE.name == ".ingest_manifest.json"