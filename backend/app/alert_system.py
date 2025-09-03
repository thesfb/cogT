# backend/app/telegram_alert.py - Fixed version

import asyncio
import json
import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional
import requests

class TelegramAlertSystem:
    """Simple, free Telegram-only alert system"""
    
    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ Telegram credentials missing. Alerts will be console-only.")
            self.telegram_enabled = False
        else:
            self.telegram_enabled = True
            print("✅ Telegram alerts enabled")
    
    def classify_threat(self, dissonance_score: float = 0, drift_score: float = 0, 
                       content: str = "") -> Dict:
        """Simple threat classification - returns plain dict"""
        
        # Critical keywords that boost threat score
        critical_keywords = ["death", "kill", "bomb", "attack", "doxx", "leak", "hack", "threat"]
        high_keywords = ["fake", "fraud", "scam", "imposter", "lie", "false"]
        
        # Start with max of dissonance or normalized drift score
        base_score = max(dissonance_score, drift_score / 10)
        
        # Boost score based on keywords
        content_lower = content.lower()
        if any(word in content_lower for word in critical_keywords):
            base_score = min(10.0, base_score + 3.0)
        elif any(word in content_lower for word in high_keywords):
            base_score = min(10.0, base_score + 1.5)
        
        # Classify threat level - return string instead of enum
        if base_score >= 9.0:
            return {"level": "critical", "score": base_score}
        elif base_score >= 7.0:
            return {"level": "high", "score": base_score}
        elif base_score >= 5.0:
            return {"level": "medium", "score": base_score}
        else:
            return {"level": "low", "score": base_score}
    
    async def send_telegram_alert(self, threat_data: Dict) -> Dict:
        """Send alert via Telegram"""
        try:
            if not self.telegram_enabled:
                return {"status": "skipped", "reason": "telegram_disabled"}
            
            threat_level = threat_data['classification']['level'].upper()
            
            # Telegram formatting with emojis
            emoji_map = {
                "CRITICAL": "🚨🔥",
                "HIGH": "⚠️🔴", 
                "MEDIUM": "⚡🟡",
                "LOW": "ℹ️🟢"
            }
            
            # Create alert message
            message = f"""
{emoji_map.get(threat_level, "ℹ️")} *{threat_level} THREAT DETECTED*

*VIP:* @{threat_data.get('vip_handle')}
*Threat Score:* {threat_data['classification']['score']:.1f}/10
*Platform:* {threat_data.get('platform', 'Unknown')}

*Content:*
```
{threat_data.get('content', 'N/A')[:400]}...
```

*AI Analysis:*
_{threat_data.get('analysis_reason', 'Analysis completed')}_

*Evidence Details:*
• Evidence ID: `{threat_data.get('evidence_id', 'N/A')}`
• Timestamp: {threat_data.get('timestamp', 'N/A')}
• Blockchain Hash: `{threat_data.get('blockchain_hash', 'N/A')[:16]}...`

🛡️ _VIP Guardian - Real-time Threat Protection_
            """
            
            # Send to Telegram
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            return {"status": "sent", "channel": "telegram", "message_id": response.json().get("result", {}).get("message_id")}
            
        except Exception as e:
            return {"status": "failed", "channel": "telegram", "error": str(e)}
    
    def send_console_alert(self, threat_data: Dict) -> Dict:
        """Fallback console alert"""
        try:
            threat_level = threat_data['classification']['level'].upper()
            
            # ANSI colors for console
            colors = {
                "CRITICAL": "\033[91m",  # Red
                "HIGH": "\033[93m",      # Yellow  
                "MEDIUM": "\033[94m",    # Blue
                "LOW": "\033[92m",       # Green
                "RESET": "\033[0m"
            }
            
            color = colors.get(threat_level, colors["RESET"])
            reset = colors["RESET"]
            
            print(f"""
{color}🚨 {threat_level} THREAT ALERT 🚨{reset}
VIP: @{threat_data.get('vip_handle')} | Score: {threat_data['classification']['score']:.1f}/10
Platform: {threat_data.get('platform', 'Unknown')}

Content: {threat_data.get('content', 'N/A')[:200]}...

Analysis: {threat_data.get('analysis_reason', 'N/A')}
Evidence ID: {threat_data.get('evidence_id', 'N/A')}
{color}{"="*60}{reset}
            """)
            
            return {"status": "sent", "channel": "console"}
        except Exception as e:
            return {"status": "failed", "channel": "console", "error": str(e)}

class SimpleEvidenceVault:
    """Lightweight evidence storage"""
    
    def __init__(self):
        self.evidence_dir = "evidence_vault"
        os.makedirs(self.evidence_dir, exist_ok=True)
    
    def capture_evidence(self, content: str, metadata: Dict) -> Dict:
        """Capture evidence with cryptographic proof"""
        timestamp = datetime.now().isoformat()
        evidence_id = hashlib.sha256(f"{content}{timestamp}".encode()).hexdigest()[:16]
        
        evidence = {
            "id": evidence_id,
            "timestamp": timestamp,
            "content": content,
            "metadata": metadata,
            "integrity_hash": hashlib.sha256(content.encode()).hexdigest(),
            "blockchain_simulation": hashlib.sha256(f"{content}{timestamp}vip_guardian".encode()).hexdigest()
        }
        
        # Save to file
        with open(f"{self.evidence_dir}/{evidence_id}.json", 'w') as f:
            json.dump(evidence, f, indent=2)
        
        return {
            "evidence_id": evidence_id,
            "blockchain_hash": evidence["blockchain_simulation"],
            "capture_time": timestamp,
            "integrity_hash": evidence["integrity_hash"]
        }

class SimpleCrisisEngine:
    """Streamlined crisis response with Telegram alerts"""
    
    def __init__(self):
        self.telegram_alerts = TelegramAlertSystem()
        self.evidence_vault = SimpleEvidenceVault()
        self.active_alerts = {}
    
    async def process_threat(self, analysis_result: Dict, content: str, 
                           vip_handle: str, platform: str = "unknown", 
                           url: str = None) -> Dict:
        """Main threat processing pipeline"""
        try:
            # Get scores from analysis
            dissonance_score = analysis_result.get('score', 0)
            drift_score = analysis_result.get('drift_score', 0)
            
            # Classify threat level
            classification = self.telegram_alerts.classify_threat(
                dissonance_score=dissonance_score,
                drift_score=drift_score,
                content=content
            )
            
            # Capture evidence
            evidence_data = self.evidence_vault.capture_evidence(
                content=content,
                metadata={
                    "vip_handle": vip_handle,
                    "platform": platform,
                    "url": url,
                    "analysis_result": analysis_result,
                    "classification": classification
                }
            )
            
            # Prepare threat data
            threat_data = {
                "vip_handle": vip_handle,
                "content": content,
                "platform": platform,
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "classification": classification,
                "analysis_reason": analysis_result.get('justification', 'AI analysis completed'),
                "evidence_id": evidence_data["evidence_id"],
                "blockchain_hash": evidence_data["blockchain_hash"]
            }
            
            # Send alerts
            alert_results = []
            
            # Always show console alert
            console_result = self.telegram_alerts.send_console_alert(threat_data)
            alert_results.append(console_result)
            
            # Send Telegram alert for medium+ threats
            if classification["level"] in ["medium", "high", "critical"]:
                telegram_result = await self.telegram_alerts.send_telegram_alert(threat_data)
                alert_results.append(telegram_result)
            
            # Store alert
            alert_id = evidence_data["evidence_id"]
            self.active_alerts[alert_id] = {
                "threat_data": threat_data,
                "alert_results": alert_results,
                "created_at": datetime.now().isoformat()
            }
            
            return {
                "alert_id": alert_id,
                "threat_level": classification["level"],
                "threat_score": classification["score"],
                "evidence_captured": True,
                "evidence_id": evidence_data["evidence_id"],
                "telegram_sent": any(r.get("channel") == "telegram" and r["status"] == "sent" for r in alert_results),
                "blockchain_hash": evidence_data["blockchain_hash"],
                "total_cost": "$0.00"
            }
            
        except Exception as e:
            raise Exception(f"Threat processing failed: {str(e)}")
    
    def get_alert_status(self, alert_id: str) -> Dict:
        """Get alert details"""
        return self.active_alerts.get(alert_id, {"error": "Alert not found"})