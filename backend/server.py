
import sys
import os
import shutil
import io
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uvicorn
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add src to path if needed (logic from main.py)
# src_path = ...
# assuming running from root or module

from backend.extractor import Extractor, StudentInfo
from backend.config_schema import AttendCheckConfig
from backend.writer import CSVWriter

# Lazy load yomitoku to avoid overhead if not needed immediately (though we need it for startup)
from yomitoku.document_analyzer import DocumentAnalyzer
from yomitoku.data.functions import load_image, load_pdf

# Global State
analyzer = None
extractor = None
executor = ThreadPoolExecutor(max_workers=4)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load Model
    global analyzer, extractor
    print("Loading Yomitoku Model...")
    try:
        # Check for CUDA
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        analyzer = DocumentAnalyzer(device=device, visualize=False)
        
        # Initialize Extractor with default config
        # TODO: Allow passing config via API?
        config = AttendCheckConfig()
        extractor = Extractor(config)
        print("Model Loaded Successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS (Allow local frontend dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production limit this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeResponse(BaseModel):
    results: List[StudentInfo]

@app.post("/api/analyze")
async def analyze_images(files: List[UploadFile] = File(...)):
    if not analyzer or not extractor:
        raise HTTPException(status_code=503, detail="Model not loaded")

    all_students = []

    for file in files:
        try:
            contents = await file.read()
            filename = file.filename
            
            # Save temp file because yomitoku load_image/pdf expects path usually?
            # load_image checks if input is str, Path, or numpy. 
            # If we decode bytes to numpy, we can skip saving.
            # But pdf loading usually requires file path or bytes (if supported).
            # yomitoku pypdfium2 logic supports bytes? loading.py says:
            # if isinstance(input_data, (str, Path)): ...
            # Let's save to temp for robustness.
            
            temp_path = f"tmp/img/{filename}"
            with open(temp_path, "wb") as f:
                f.write(contents)
                
            imgs = []
            if filename.lower().endswith(".pdf"):
                imgs = load_pdf(temp_path)
            else:
                imgs = load_image(temp_path) # returns list
            
            for img in imgs:
                # Run synchronous analyzer in thread pool to avoid event loop conflict
                loop = asyncio.get_event_loop()
                result, _, _ = await loop.run_in_executor(executor, analyzer, img)
                students = extractor.extract(result, file_name=filename)
                all_students.extend(students)
            
        except Exception as e:
            print(f"Error processing {file.filename}: {e}")
            # continue or error? Let's return what we have so far or partially failed?
            # For now just print error.

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    return {"results": [s.model_dump() for s in all_students]}

class ExportRequest(BaseModel):
    students: List[dict] # Receive the list back

@app.post("/api/export")
async def export_csv(req: ExportRequest):
    # Convert dicts back to StudentInfo (optional, writer takes dicts? No, logic uses StudentInfo object usually)
    # CSVWriter.write_merged expects List[StudentInfo]
    
    # Reconstruct objects
    student_objs = []
    for s_data in req.students:
        # Handle optional fields
        s_data.setdefault("file_name", None)
        student_objs.append(StudentInfo(**s_data))

    # Write to string buffer
    output = io.StringIO()
    # writer.py uses csv.DictWriter which needs a file-like object.
    # write_merged takes output_path (string). Refactor writer? 
    # Or just write to temp and read back.
    
    temp_csv = "temp_export.csv"
    CSVWriter.write_merged(student_objs, temp_csv)
    
    with open(temp_csv, "r", encoding="utf-8-sig") as f:
        content = f.read()
    
    os.remove(temp_csv)
    
    return JSONResponse(content={"csv": content}) 
    # Or return StreamingResponse for file download
    # return StreamingResponse(
    #     iter([content]),
    #     media_type="text/csv",
    #     headers={"Content-Disposition": "attachment; filename=results.csv"}
    # )

@app.post("/api/export/download")
async def export_download(req: ExportRequest):
    student_objs = []
    for s_data in req.students:
        s_data.setdefault("file_name", None)
        student_objs.append(StudentInfo(**s_data))

    temp_csv = "temp_export.csv"
    CSVWriter.write_merged(student_objs, temp_csv)
    
    # We need to read binary for StreamingResponse properly? Or text.
    # utf-8-sig adds BOM.
    
    def iterfile():
        with open(temp_csv, "rb") as f:
            yield from f
        os.remove(temp_csv)

    return StreamingResponse(
        iterfile(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"}
    )

# Static Files (Frontend)
# logic: if "ui/dist" exists, mount it.
ui_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../ui/dist")
if os.path.exists(ui_dist):
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
