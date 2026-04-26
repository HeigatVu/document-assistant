import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# This will fail to import initially
from tools.task import process_task, TaskResult

@patch("tools.task.search_index")
@patch("tools.task._call_gemini")
@patch("tools.task.edit_docx")
@patch("tools.task.create_docx")
def test_process_task_create_from_prompt(mock_create, mock_edit, mock_gemini, mock_search, tmp_path):
    # Mock search returning one reference
    mock_search.return_value = [{"file": "ref.docx", "summary": "A document", "folder_path": str(tmp_path)}]
    
    # Mock the two Gemini calls: the planning phase and the writing phase
    mock_gemini.side_effect = [
        "Plan: Gather facts",
        '{"title": "New Doc", "content": "Hello world"}'
    ]
    
    save_path = tmp_path / "output.docx"
    
    # Execute
    result = process_task(
        prompt="Write a greeting based on ref.docx",
        uploaded_file_path=None,
        reading_model="gemini-1.5-pro",
        writing_model="gemini-1.5-flash",
        save_path=save_path
    )
    
    # Verify
    assert isinstance(result, TaskResult)
    assert result.success is True
    assert result.output_path == save_path
    assert "ref.docx" in result.referenced_files
    
    # Verify we called the correct writer function
    mock_create.assert_called_once()
    mock_edit.assert_not_called()
