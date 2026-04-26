import time
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from tools.utils import RAW_DIR
from tools.task import process_task

app = FastAPI(title="Wiki LLM Document Assistant")

# Enable CORS for the future Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    prompt: str
    reading_model: str = "gemini-1.5-pro"
    writing_model: str = "gemini-1.5-flash"
    uploaded_file: Optional[str] = None

def list_documents() -> list[str]:
    """List documents in RAW_DIR."""
    if not RAW_DIR.exists():
        return []
    
    docs = []
    for ext in ("*.pdf", "*.docx"):
        for path in RAW_DIR.rglob(ext):
            try:
                rel_path = str(path.relative_to(RAW_DIR))
                docs.append(rel_path)
            except ValueError:
                docs.append(path.name)
    return docs

@app.get("/api/status")
def get_status():
    return {"status": "ok"}

@app.get("/api/documents")
def get_documents():
    return {"documents": list_documents()}

@app.post("/api/task")
def post_task(req: TaskRequest):
    output_path = RAW_DIR / f"output_{int(time.time())}.docx"
    
    uploaded_file_path = None
    if req.uploaded_file:
        uploaded_file_path = RAW_DIR / req.uploaded_file
        if not uploaded_file_path.exists():
            raise HTTPException(status_code=400, detail="Uploaded file not found")
            
    try:
        result = process_task(
            prompt=req.prompt,
            uploaded_file_path=uploaded_file_path,
            reading_model=req.reading_model,
            writing_model=req.writing_model,
            save_path=output_path
        )
        
        return {
            "success": result.success,
            "summary": result.summary,
            "output_file": str(result.output_path.name),
            "referenced_files": result.referenced_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
