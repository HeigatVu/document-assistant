import os
import time
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Union

from tools.task import process_task
from tools.ingest import ingest
from tools.utils import RAW_DIR, OUTPUT_DIR, load_manifest, HISTORY_FILE, INDEX_FILE
from tools.config import DEFAULT_READING_MODEL, DEFAULT_WRITING_MODEL
import json
import uuid

app = FastAPI(title="Wiki LLM Document Assistant")

# Enable CORS for the future Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    prompt: str
    reading_model: str = DEFAULT_READING_MODEL
    writing_model: str = DEFAULT_WRITING_MODEL
    uploaded_file: Optional[str] = None
    template_file: Optional[str] = None
    type_filter: Optional[str] = None
    use_cli: bool = False

class IngestRequest(BaseModel):
    filename: str

class OpenRequest(BaseModel):
    filename: str

class OpenOutputRequest(BaseModel):
    filename: str

class OpenOutputFolderRequest(BaseModel):
    filename: str

class DeleteTaskRequest(BaseModel):
    id: Union[int, str]
    filename: str

def load_history() -> list[dict]:
    """Load task history from JSON file."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return []
    return []

def append_history(entry: dict):
    """Append a new entry to the history file, keeping only entries from the last 60 days."""
    history = load_history()
    history.append(entry)

    current_time = time.time()
    sixty_days_seconds = 60 * 24 * 60 * 60

    filtered_history = []
    for item in history:
        item_time = item.get("id")
        # Handle legacy (seconds), milliseconds (1e12), and nanoseconds (1e18)
        if isinstance(item_time, (int, float)):
            if item_time > 1e15: # Nanoseconds
                actual_time = item_time / 1_000_000_000.0
            elif item_time > 1e11: # Milliseconds
                actual_time = item_time / 1000.0
            else: # Seconds
                actual_time = item_time
            if current_time - actual_time > sixty_days_seconds:
                continue
        filtered_history.append(item)

    HISTORY_FILE.write_text(json.dumps(filtered_history, indent=2), encoding="utf-8")
def list_documents() -> list[dict]:
    """List documents in RAW_DIR."""
    if not RAW_DIR.exists():
        return []
    
    manifest = load_manifest()
    docs = []
    # Case-insensitive scan
    for path in RAW_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".pdf", ".docx"):
            try:
                # Use absolute resolution to match ingest script logic
                resolved_path = path.resolve()
                rel_path = str(resolved_path.relative_to(RAW_DIR))
                
                # Check status: check relative path first, then filename fallback for legacy entries
                is_ingested = rel_path in manifest or path.name in manifest
                status = "ingested" if is_ingested else "pending"
                
                docs.append({"name": rel_path, "status": status})
            except ValueError:
                docs.append({"name": path.name, "status": "pending"})
    return docs

@app.get("/api/types")
def get_types():
    if not INDEX_FILE.exists():
        return {"types": []}
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        types = sorted(list(set(d.get("Type") for d in data if d.get("Type") and d.get("Type") != "Unknown")))
        return {"types": types}
    except Exception:
        return {"types": []}

@app.get("/api/history")
def get_history():
    return {"history": load_history()[::-1]} 

@app.get("/api/status")
def get_status():
    return {"status": "ok"}

@app.get("/api/documents")
def get_documents():
    return {"documents": list_documents()}

@app.post("/api/open_dir")
def post_open_dir():
    try:
        import subprocess
        import sys
        if sys.platform == "win32":
            os.startfile(RAW_DIR)
        elif sys.platform == "darwin":
            subprocess.call(["open", str(RAW_DIR)])
        else:
            subprocess.call(["xdg-open", str(RAW_DIR)])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/open")
def post_open(req: OpenRequest):
    requested_path = (RAW_DIR / req.filename).resolve()
    if RAW_DIR.resolve() not in requested_path.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not requested_path.exists():
        raise HTTPException(status_code=400, detail="File not found")
        
    try:
        import subprocess
        import sys
        if sys.platform == "win32":
            os.startfile(requested_path)
        elif sys.platform == "darwin":
            subprocess.call(["open", str(requested_path)])
        else:
            subprocess.call(["xdg-open", str(requested_path)])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/open_output")
def post_open_output(req: OpenOutputRequest):
    requested_path = (OUTPUT_DIR / req.filename).resolve()
    if OUTPUT_DIR.resolve() not in requested_path.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not requested_path.exists():
        raise HTTPException(status_code=400, detail="File not found")
        
    try:
        import subprocess
        import sys
        if sys.platform == "win32":
            os.startfile(requested_path)
        elif sys.platform == "darwin":
            subprocess.call(["open", str(requested_path)])
        else:
            subprocess.call(["xdg-open", str(requested_path)])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/open_output_folder")
def post_open_output_folder(req: OpenOutputFolderRequest):
    requested_path = (OUTPUT_DIR / req.filename).resolve()
    if OUTPUT_DIR.resolve() not in requested_path.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    # Open the parent directory
    folder_path = requested_path.parent
    if not folder_path.exists():
        raise HTTPException(status_code=400, detail="Folder not found")
        
    try:
        import subprocess
        import sys
        if sys.platform == "win32":
            os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.call(["open", str(folder_path)])
        else:
            subprocess.call(["xdg-open", str(folder_path)])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/delete_task")
def post_delete_task(req: DeleteTaskRequest):
    # 1. Delete history entry
    history = load_history()
    new_history = [h for h in history if h.get("id") != req.id]
    HISTORY_FILE.write_text(json.dumps(new_history, indent=2), encoding="utf-8")
    
    # 2. Delete file if it exists
    try:
        file_path = (OUTPUT_DIR / req.filename).resolve()
        if OUTPUT_DIR.resolve() in file_path.parents and file_path.exists():
            file_path.unlink()
    except Exception:
        pass # Ignore file deletion errors if file is already gone
        
    return {"success": True}

from fastapi.responses import StreamingResponse
import asyncio

@app.post("/api/task")
async def post_task_endpoint(req: TaskRequest):
    if req.use_cli:
        # For CLI mode, we stream the output of the process_task steps
        async def stream_task():
            # Run the task in a separate thread/process to not block the event loop
            # and capture its stdout for real-time streaming.
            import subprocess
            import sys
            
            # Construct the command to run tools/task.py as a script
            cmd = [sys.executable, "tools/task.py", req.prompt, "--cli"]
            if req.template_file:
                cmd.extend(["--template", req.template_file])
            if req.type_filter:
                cmd.extend(["--type", req.type_filter])
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            last_history_entry = None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                decoded_line = line.decode().strip()
                # Yield the line for the frontend to process
                yield f"data: {decoded_line}\n\n"
                
                # Check if this is the final result JSON
                try:
                    if decoded_line.startswith('{"id":'):
                        last_history_entry = json.loads(decoded_line)
                except:
                    pass
            
            await process.wait()

        return StreamingResponse(stream_task(), media_type="text/event-stream")
    else:
        # Standard API path (no streaming)
        output_path = OUTPUT_DIR / f"output_{int(time.time())}.docx"

        template_file_path = None
        uploaded_file_path = None
        if req.template_file:
            t_requested_path = (RAW_DIR / req.template_file).resolve()
            if RAW_DIR.resolve() not in t_requested_path.parents:
                raise HTTPException(status_code=400, detail="Invalid template path")
            template_file_path = t_requested_path
            if not template_file_path.exists():
                raise HTTPException(status_code=400, detail="Template file not found")
                
        if req.uploaded_file:
            requested_path = (RAW_DIR / req.uploaded_file).resolve()
            if RAW_DIR.resolve() not in requested_path.parents:
                raise HTTPException(status_code=400, detail="Invalid file path")
            uploaded_file_path = requested_path
            if not uploaded_file_path.exists():
                raise HTTPException(status_code=400, detail="Uploaded file not found")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: process_task(
                    prompt=req.prompt,
                    uploaded_file_path=uploaded_file_path,
                    template_file_path=template_file_path, 
                    reading_model=req.reading_model,
                    writing_model=req.writing_model,
                    save_path=output_path,
                    type_filter=req.type_filter,
                    use_cli=req.use_cli
                )
            )
            
            history_entry = {
                "id": time.time_ns(),
                "prompt": req.prompt,
                "summary": result.summary,
                "output_file": str(result.output_path.name),
                "referenced_files": result.referenced_files,
                "success": result.success,
                "created_at": time.strftime("%Y-%m-%d %H:%M")
            }
            append_history(history_entry)
            return history_entry 
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest")
def post_ingest(req: IngestRequest):
    # Resolve and verify path (security check)
    requested_path = (RAW_DIR / req.filename).resolve()
    if RAW_DIR.resolve() not in requested_path.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not requested_path.exists():
        raise HTTPException(status_code=400, detail="File not found")
        
    try:
        # Trigger ingestion
        ingest(requested_path)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Save the file to RAW_DIR with path traversal protection
    # We use path.name to strip any directory components
    from pathlib import Path
    safe_filename = Path(file.filename).name
    file_path = (RAW_DIR / safe_filename).resolve()

    # Double check that the resolved path is inside RAW_DIR
    if RAW_DIR.resolve() not in file_path.parents:
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
        return {"filename": safe_filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
