# backend/main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict

import threading
import time
import chromadb

# Import specific scanner function instead of the continuous runner
from app.scanner import scan_reddit_for_mentions
from app.telegram_monitor import TelegramMonitor

# --- Import existing modules ---
from app.twin_builder import build_and_store_twin
from app.analysis import check_dissonance, check_stylometric_drift
from app.alert_system import SimpleCrisisEngine

# --- Import NEW visual analysis module ---
from app.visual_analysis import get_image_fingerprint_from_url, analyze_image_content_from_url, transcribe_audio_from_video_url

# Create the FastAPI app
app = FastAPI(title="VIP Guardian API", version="3.2.0 Manual Scan")

# Initialize crisis engine
crisis_engine = SimpleCrisisEngine()

# --- CORS Middleware ---
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
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

# UPDATED ThreatAnalysisRequest to include fake account data
class ThreatAnalysisRequest(BaseModel):
    twitter_handle: str
    text_to_check: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    platform: Optional[str] = "unknown"
    source_url: Optional[str] = None
    enable_alerts: Optional[bool] = True
    fake_account_analysis: Optional[Dict] = None # INTEGRATION: Add field for fake account data

class DissonanceRequest(BaseModel):
    twitter_handle: str
    text_to_check: str

class DriftRequest(BaseModel):
    twitter_handle: str
    text_to_check: str

# --- Health Check ---
@app.get("/")
def read_root():
    return {
        "status": "VIP Guardian Backend Online 🛡️",
        "version": "3.2.0 Manual Scan",
        "features": ["cognitive_twins", "text_analysis", "visual_analysis", "telegram_alerts", "evidence_vault", "manual_scanners"],
    }

@app.get("/health")
def health_check():
    telegram_status = "enabled" if crisis_engine.telegram_alerts.telegram_enabled else "console_fallback"
    return {
        "status": "healthy",
        "services": {
            "database": "connected (ChromaDB)",
            "ai_models": "loaded (Gemini, SentenceTransformer, GCP Vision/Speech)",
            "telegram_alerts": telegram_status,
            "evidence_vault": "ready (local)"
        }
    }

# --- Twin Management ---
@app.post("/build-twin")
def build_twin_endpoint(request: TwinRequest):
    try:
        result = build_and_store_twin(request.twitter_handle)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Main Multi-Modal Analysis Endpoint ---
@app.post("/analyze/threat")
async def comprehensive_threat_analysis(request: ThreatAnalysisRequest):
    """
    Main endpoint for multi-modal threat analysis (text, image, video).
    """
    try:
        vip_handle = request.twitter_handle
        full_content = request.text_to_check
        
        # --- 1. Text Analysis (Baseline) ---
        dissonance_result = check_dissonance(vip_handle, full_content)
        drift_result = check_stylometric_drift(vip_handle, full_content)
        
        if dissonance_result.get("error"):
            dissonance_result = {"score": 0, "justification": "Could not perform dissonance check; twin may not cover this topic."}
        if drift_result.get("error"):
            drift_result = {"drift_score": 0}

        # --- 2. Visual Analysis (Conditional) ---
        visual_analysis_details = {}
        ocr_dissonance_score = 0
        transcript_dissonance_score = 0

        if request.image_url:
            fingerprint = get_image_fingerprint_from_url(request.image_url)
            content_analysis = analyze_image_content_from_url(request.image_url)
            visual_analysis_details["image"] = { "perceptual_hash": fingerprint, **content_analysis }
            if content_analysis.get("ocr_text"):
                ocr_dissonance = check_dissonance(vip_handle, content_analysis["ocr_text"])
                ocr_dissonance_score = ocr_dissonance.get("score", 0)

        if request.video_url:
            transcript = transcribe_audio_from_video_url(request.video_url)
            visual_analysis_details["video"] = { "audio_transcript": transcript }
            if transcript:
                transcript_dissonance = check_dissonance(vip_handle, transcript)
                transcript_dissonance_score = transcript_dissonance.get("score", 0)

        # --- 3. Combine and Score ---
        dissonance_score = dissonance_result.get("score", 0)
        drift_score = drift_result.get("drift_score", 0)
        visual_threat_score = max(ocr_dissonance_score, transcript_dissonance_score)

        combined_analysis = {
            "dissonance_score": dissonance_score,
            "drift_score": drift_score,
            "visual_threat_score": visual_threat_score,
            "justification": dissonance_result.get("justification", "Analysis completed."),
            "visual_details": visual_analysis_details
        }

        # --- 4. Process Alerts ---
        if request.enable_alerts:
            threat_response = await crisis_engine.process_threat(
                analysis_result=combined_analysis,
                content=full_content,
                vip_handle=vip_handle,
                platform=request.platform,
                url=request.source_url,
                fake_account_analysis=request.fake_account_analysis
            )
            return {"analysis": combined_analysis, "threat_response": threat_response}
        else:
            return {"analysis": combined_analysis, "alert_system": "disabled"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# --- Legacy/Debug Analysis Endpoints ---
@app.post("/analyze/dissonance")
def analyze_dissonance_endpoint(request: DissonanceRequest):
    return check_dissonance(request.twitter_handle, request.text_to_check)

@app.post("/analyze/drift")
def analyze_drift_endpoint(request: DriftRequest):
    return check_stylometric_drift(request.twitter_handle, request.text_to_check)

# --- Evidence & Alert Management ---
@app.get("/alerts/{alert_id}")
def get_alert_details(alert_id: str):
    result = crisis_engine.get_alert_status(alert_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/evidence/{evidence_id}")
def get_evidence_details(evidence_id: str):
    try:
        import json
        import os
        evidence_file = f"evidence_vault/{evidence_id}.json"
        if not os.path.exists(evidence_file):
            raise HTTPException(status_code=404, detail="Evidence not found")
        with open(evidence_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Telegram Setup Helper ---
@app.get("/setup/telegram")
def telegram_setup_guide():
    return { "message": "See documentation for setting up Telegram bot tokens for alerts (TELEGRAM_BOT_TOKEN) and monitoring (TELEGRAM_MONITOR_BOT_TOKEN)." }

# --- Manual Scanner Logic ---
def perform_reddit_scan():
    """Performs a single scan cycle on Reddit for all monitored VIPs."""
    print("\n--- Triggering single Reddit scan cycle ---")
    chroma_client = chromadb.PersistentClient(path="./db")
    subreddits_to_scan = ['politics', 'worldnews', 'news', 'technology', 'conspiracy']
    
    collections = chroma_client.list_collections()
    monitored_vips = [col.name.replace("vip_", "") for col in collections]

    if not monitored_vips:
        print("[Scanner] No VIP twins found for Reddit scan. Skipping.")
        return
    
    print(f"[Scanner] Monitoring {len(monitored_vips)} VIPs on Reddit: {', '.join(monitored_vips)}")
    for vip in monitored_vips:
        scan_reddit_for_mentions(vip, subreddits_to_scan)
    print("--- Reddit scan cycle complete. ---")


def perform_telegram_scan():
    """Performs a single scan cycle on Telegram for all monitored VIPs."""
    print("\n--- Triggering single Telegram scan cycle ---")
    chroma_client = chromadb.PersistentClient(path="./db")
    telegram_monitor = TelegramMonitor()

    collections = chroma_client.list_collections()
    monitored_vips = [col.name.replace("vip_", "") for col in collections]

    if not monitored_vips:
        print("[Telegram Scanner] No VIP twins found. Skipping.")
        return

    print(f"[Telegram Scanner] Monitoring {len(monitored_vips)} VIPs: {', '.join(monitored_vips)}")
    impersonators = telegram_monitor.detect_impersonation_channels(monitored_vips)
    if impersonators:
        print(f"Found {len(impersonators)} potential impersonation channels. Processing...")
        for vip in monitored_vips:
            vip_impersonators = [imp for imp in impersonators if imp.get('target_vip') == vip]
            telegram_monitor.process_telegram_mentions(vip_impersonators, vip)

    for vip in monitored_vips:
        mentions = telegram_monitor.scan_all_channels_for_vip(vip)
        if mentions:
            print(f"Found {len(mentions)} potential mentions on Telegram for {vip}. Processing...")
            telegram_monitor.process_telegram_mentions(mentions, vip)

    print(f"--- Telegram scan cycle complete. ---")

# --- New Endpoint to Trigger Scanners ---
@app.post("/scanners/trigger", status_code=202)
def trigger_scanners(background_tasks: BackgroundTasks):
    """
    Triggers a one-time scan for all VIPs on both Reddit and Telegram.
    The scans run in the background.
    """
    print("API call received to trigger scanners.")
    background_tasks.add_task(perform_reddit_scan)
    background_tasks.add_task(perform_telegram_scan)
    return {"message": "Scanners for Reddit and Telegram have been triggered in the background."}


@app.on_event("startup")
async def startup_event():
    """Handles all startup tasks for the application."""
    print("🚀 VIP Guardian Backend Starting...")
    
    print("✅ Scanners are on standby. Trigger them via the POST /scanners/trigger endpoint.")

    # Check Telegram alert status
    if crisis_engine.telegram_alerts.telegram_enabled:
        print("✅ Telegram alerts: ACTIVE")
    else:
        print("⚠️ Telegram alerts: Console fallback (add TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID to .env)")
    
    print("✅ Evidence vault: Ready")
    print("🛡️ VIP Guardian is protecting your digital presence!")

    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

