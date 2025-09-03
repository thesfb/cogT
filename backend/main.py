# In backend/main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Import our new analysis function ---
from app.twin_builder import build_and_store_twin
from app.analysis import check_dissonance
from app.twin_builder import build_and_store_twin
from app.analysis import check_dissonance, check_stylometric_drift

# Create the FastAPI app instance
app = FastAPI()

# --- CORS Middleware ---
origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class TwinRequest(BaseModel):
    twitter_handle: str

class DissonanceRequest(BaseModel):
    twitter_handle: str
    text_to_check: str

class DriftRequest(BaseModel):
    twitter_handle: str
    text_to_check: str

@app.get("/")
def read_root():
    return {"status": "Backend is running!"}

@app.post("/build-twin")
def build_twin_endpoint(request: TwinRequest):
    try:
        result = build_and_store_twin(request.twitter_handle)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- UPDATE THIS ENDPOINT ---
@app.post("/analyze/dissonance")
def analyze_dissonance_endpoint(request: DissonanceRequest):
    try:
        result = check_dissonance(request.twitter_handle, request.text_to_check)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/drift")
def analyze_drift_endpoint(request: DriftRequest):
    try:
        result = check_stylometric_drift(request.twitter_handle, request.text_to_check)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))