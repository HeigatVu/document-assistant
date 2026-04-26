import time
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from tools.task import process_task
from tools.ingest import ingest
from tools.utils import RAW_DIR, OUTPUT_DIR, load_manifest, HISTORY_FILE
import json

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
    reading_model: str = "gemini-1.5-pro"
    writing_model: str = "gemini-1.5-flash"
    uploaded_file: Optional[str] = None
    template_file: Optional[str] = None 

class IngestRequest(BaseModel):
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
    """Append a new entry to the history file."""
    history = load_history()
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")

def list_documents() -> list[str]:
    """List documents in RAW_DIR."""
    if not RAW_DIR.exists():
        return []
    
    manifest = load_manifest()
    docs = []
    for ext in ("*.pdf", "*.docx"):
        for path in RAW_DIR.rglob(ext):
            try:
                rel_path = str(path.relative_to(RAW_DIR))
                # Check status
                status = "ingested" if rel_path in manifest else "pending"
                docs.append({"name": rel_path, "status": status})
            except ValueError:
                docs.append({"name": path.name, "status": "pending"})
    return docs

@app.get("/api/history")
def get_history():
    return {"history": load_history()[::-1]} 

@app.get("/api/status")
def get_status():
    return {"status": "ok"}

@app.get("/api/documents")
def get_documents():
    return {"documents": list_documents()}

@app.post("/api/task")
def post_task(req: TaskRequest):
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
        result = process_task(
            prompt=req.prompt,
            uploaded_file_path=uploaded_file_path,
            template_file_path=template_file_path, 
            reading_model=req.reading_model,
            writing_model=req.writing_model,
            save_path=output_path
        )
        
        history_entry = {
            "id": int(time.time()),
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
    
    # Save the file to RAW_DIR
    file_path = RAW_DIR / file.filename
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
        return {"filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
