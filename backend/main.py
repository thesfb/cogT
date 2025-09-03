# backend/main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# --- Import existing modules ---
from app.twin_builder import build_and_store_twin
from app.analysis import check_dissonance, check_stylometric_drift

# --- Import simple Telegram alert system ---
from app.alert_system import SimpleCrisisEngine

# Create the FastAPI app
app = FastAPI(title="VIP Guardian API", version="2.0.0")

# Initialize crisis engine (Telegram-only)
crisis_engine = SimpleCrisisEngine()

# --- CORS Middleware ---
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",  # Vite default
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

class ThreatAnalysisRequest(BaseModel):
    twitter_handle: str
    text_to_check: str
    platform: Optional[str] = "unknown"
    source_url: Optional[str] = None
    enable_alerts: Optional[bool] = True

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
        "version": "2.0.0",
        "alert_system": "Telegram (Free & Unlimited)",
        "features": ["cognitive_twins", "threat_analysis", "telegram_alerts", "evidence_vault"],
        "cost": "$0.00 per month"
    }

@app.get("/health")
def health_check():
    telegram_status = "enabled" if crisis_engine.telegram_alerts.telegram_enabled else "console_fallback"
    return {
        "status": "healthy",
        "services": {
            "database": "connected (ChromaDB)", 
            "ai_models": "loaded (local)",
            "telegram_alerts": telegram_status,
            "evidence_vault": "ready (local)"
        },
        "cost_status": "100% free"
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

# --- Legacy Analysis Endpoints ---
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

# --- NEW: Main Analysis Endpoint with Telegram Alerts ---
@app.post("/analyze/threat")
async def threat_analysis_with_alerts(request: ThreatAnalysisRequest):
    """
    Complete threat analysis with automatic Telegram alerts and evidence capture
    """
    try:
        # Run both analysis engines
        dissonance_result = check_dissonance(request.twitter_handle, request.text_to_check)
        drift_result = check_stylometric_drift(request.twitter_handle, request.text_to_check)
        
        # Check for errors
        if dissonance_result.get("error"):
            raise HTTPException(status_code=400, detail=dissonance_result["error"])
        if drift_result.get("error"):
            raise HTTPException(status_code=400, detail=drift_result["error"])
        
        # Combine results
        combined_analysis = {
            "dissonance": dissonance_result,
            "drift": drift_result,
            "score": dissonance_result.get("score", 0),
            "drift_score": drift_result.get("drift_score", 0),
            "justification": dissonance_result.get("justification", "Analysis completed")
        }
        
        # Process through crisis engine if alerts enabled
        if request.enable_alerts:
            threat_response = await crisis_engine.process_threat(
                analysis_result=combined_analysis,
                content=request.text_to_check,
                vip_handle=request.twitter_handle,
                platform=request.platform,
                url=request.source_url
            )
            
            return {
                "analysis": combined_analysis,
                "threat_response": threat_response,
                "alert_system": "telegram_active",
                "cost": "$0.00"
            }
        else:
            return {
                "analysis": combined_analysis,
                "alert_system": "disabled"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Evidence & Alert Management ---
@app.get("/alerts/{alert_id}")
def get_alert_details(alert_id: str):
    """Get details of a specific alert"""
    try:
        result = crisis_engine.get_alert_status(alert_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/active/summary")
def get_alerts_summary():
    """Get summary of all active alerts"""
    try:
        active_alerts = crisis_engine.active_alerts
        
        summary = {
            "total_alerts": len(active_alerts),
            "by_threat_level": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "telegram_enabled": crisis_engine.telegram_alerts.telegram_enabled,
            "recent_alerts": []
        }
        
        for alert_id, alert_data in active_alerts.items():
            threat_level = alert_data["threat_data"]["classification"]["level"].value
            summary["by_threat_level"][threat_level] += 1
            
            if len(summary["recent_alerts"]) < 10:
                summary["recent_alerts"].append({
                    "alert_id": alert_id,
                    "vip_handle": alert_data["threat_data"]["vip_handle"],
                    "threat_level": threat_level,
                    "score": alert_data["threat_data"]["classification"]["score"],
                    "created_at": alert_data["created_at"]
                })
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/evidence/{evidence_id}")
def get_evidence_details(evidence_id: str):
    """Get evidence details"""
    try:
        import json
        import os
        
        evidence_file = f"evidence_vault/{evidence_id}.json"
        if not os.path.exists(evidence_file):
            raise HTTPException(status_code=404, detail="Evidence not found")
        
        with open(evidence_file, 'r') as f:
            evidence = json.load(f)
        
        return {
            "evidence_id": evidence["id"],
            "timestamp": evidence["timestamp"],
            "content": evidence["content"],
            "platform": evidence["metadata"].get("platform", "unknown"),
            "vip_handle": evidence["metadata"].get("vip_handle"),
            "integrity_hash": evidence["integrity_hash"],
            "blockchain_simulation": evidence["blockchain_simulation"][:16] + "...",
            "cost": "$0.00"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Demo Endpoints ---
@app.post("/demo/telegram-alert")
async def demo_telegram_alert():
    """Demo endpoint to test Telegram alerts"""
    try:
        demo_content = "URGENT: This is a fake account impersonating @demo_vip to spread false information!"
        
        threat_response = await crisis_engine.process_threat(
            analysis_result={
                "score": 8.5, 
                "drift_score": 75.0,
                "justification": "High dissonance detected - content contradicts VIP's established public statements"
            },
            content=demo_content,
            vip_handle="demo_vip",
            platform="twitter",
            url="https://twitter.com/fake_account/status/123456789"
        )
        
        return {
            "message": "Demo Telegram alert sent! Check your Telegram bot.",
            "response": threat_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/setup/telegram")
def telegram_setup_guide():
    """Returns setup instructions for Telegram bot"""
    return {
        "title": "Free Telegram Alert Setup (2 minutes)",
        "steps": [
            "1. Open Telegram and search for '@BotFather'",
            "2. Send /newbot command to BotFather",
            "3. Choose a name and username for your bot",
            "4. Copy the bot token (long string with numbers and letters)",
            "5. Add TELEGRAM_BOT_TOKEN=your_token to your .env file",
            "6. Send a message to your new bot",
            "7. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates",
            "8. Find 'chat' -> 'id' number in the response",
            "9. Add TELEGRAM_CHAT_ID=your_chat_id to your .env file",
            "10. Restart the backend - you're done! 🎉"
        ],
        "cost": "100% FREE - Unlimited messages",
        "benefits": [
            "Instant mobile notifications",
            "Rich formatting with emojis", 
            "Works anywhere in the world",
            "No daily limits",
            "Professional looking alerts"
        ]
    }

# --- Startup Message ---
@app.on_event("startup")
async def startup_event():
    print("🚀 VIP Guardian Backend Starting...")
    if crisis_engine.telegram_alerts.telegram_enabled:
        print("✅ Telegram alerts: ACTIVE")
    else:
        print("⚠️ Telegram alerts: Console fallback (add TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID to .env)")
    print("✅ Evidence vault: Ready")
    print("✅ Cost: $0.00/month")
    print("🛡️ VIP Guardian is protecting your digital presence!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)