import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# This will fail to import initially
from server.app import app

client = TestClient(app)

def test_get_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_documents(monkeypatch):
    # Mock RAW_DIR listing
    monkeypatch.setattr("server.app.list_documents", lambda: ["doc1.pdf", "doc2.docx"])
    response = client.get("/api/documents")
    assert response.status_code == 200
    assert response.json() == {"documents": ["doc1.pdf", "doc2.docx"]}

def test_post_task(monkeypatch):
    # Mock process_task
    from tools.task import TaskResult
    mock_result = TaskResult(
        output_path=Path("output.docx"),
        summary="Task done",
        referenced_files=["doc1.pdf"],
        success=True
    )
    monkeypatch.setattr("server.app.process_task", lambda **kwargs: mock_result)
    
    response = client.post(
        "/api/task", 
        json={
            "prompt": "Write a summary", 
            "reading_model": "gemini-1.5-pro", 
            "writing_model": "gemini-1.5-flash"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["summary"] == "Task done"
