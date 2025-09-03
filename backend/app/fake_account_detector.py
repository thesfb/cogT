# backend/app/fake_account_detector.py
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import difflib

class FakeAccountDetector:
    """Detects suspicious accounts that may be impersonating VIPs"""
    
    def __init__(self):
        self.suspicious_patterns = [
            r"verified[_-]?account",
            r"real[_-]?account",  
            r"official[_-]?page",
            r"authentic[_-]?profile",
        ]
        
        # Common impersonation tactics
        self.character_substitutions = {
            'a': ['@', 'α', 'а'],  # Latin a, Cyrillic a
            'e': ['3', 'е'],       # Number 3, Cyrillic e
            'i': ['1', 'l', '!', 'і'],  # Number 1, lowercase L, Cyrillic i
            'o': ['0', 'о'],       # Zero, Cyrillic o
            'u': ['υ', 'и'],       # Greek upsilon, Cyrillic u
        }
    
    def analyze_reddit_account(self, username: str, post_data: Dict) -> Dict:
        """Analyze a Reddit account for suspicious characteristics"""
        suspicious_flags = []
        risk_score = 0.0
        
        try:
            # Get account info from Reddit API
            session = requests.Session()
            session.headers.update({'User-Agent': 'VIPGuardianScanner/1.0'})
            
            user_url = f"https://www.reddit.com/user/{username}/about.json"
            response = session.get(user_url)
            
            if response.status_code == 200:
                user_data = response.json()['data']
                account_age_days = (datetime.now() - datetime.fromtimestamp(user_data['created_utc'])).days
                
                # Flag 1: Very new accounts (less than 30 days)
                if account_age_days < 30:
                    suspicious_flags.append(f"Very new account ({account_age_days} days old)")
                    risk_score += 2.0
                
                # Flag 2: Low karma but making VIP-related posts
                total_karma = user_data.get('total_karma', 0)
                if total_karma < 100:
                    suspicious_flags.append(f"Low karma account ({total_karma} total karma)")
                    risk_score += 1.5
                
                # Flag 3: Suspicious username patterns
                username_lower = username.lower()
                for pattern in self.suspicious_patterns:
                    if re.search(pattern, username_lower):
                        suspicious_flags.append(f"Suspicious username pattern: {pattern}")
                        risk_score += 3.0
                
            else:
                suspicious_flags.append("Could not retrieve account information")
                risk_score += 1.0
                
        except Exception as e:
            suspicious_flags.append(f"Error checking account: {str(e)}")
            risk_score += 0.5
        
        # Flag 4: Check post content for impersonation claims
        post_text = f"{post_data.get('title', '')} {post_data.get('selftext', '')}"
        if self._contains_impersonation_claims(post_text):
            suspicious_flags.append("Post contains impersonation claims")
            risk_score += 4.0
        
        return {
            "username": username,
            "risk_score": min(risk_score, 10.0),  # Cap at 10
            "suspicious_flags": suspicious_flags,
            "analysis_timestamp": datetime.now().isoformat(),
            "platform": "Reddit"
        }
    
    def analyze_telegram_account(self, channel_info: Dict) -> Dict:
        """Analyze a Telegram channel for suspicious characteristics"""
        suspicious_flags = []
        risk_score = 0.0
        
        channel_name = channel_info.get('username', 'Unknown')
        title = channel_info.get('title', '')
        description = channel_info.get('description', '')
        member_count = channel_info.get('participants_count', 0)
        
        # Flag 1: Low subscriber count but claiming to be official
        if member_count < 1000 and self._contains_impersonation_claims(f"{title} {description}"):
            suspicious_flags.append(f"Low subscriber count ({member_count}) with official claims")
            risk_score += 3.0
        
        # Flag 2: Suspicious channel name patterns
        channel_lower = channel_name.lower()
        for pattern in self.suspicious_patterns:
            if re.search(pattern, channel_lower):
                suspicious_flags.append(f"Suspicious channel name pattern: {pattern}")
                risk_score += 2.5
        
        # Flag 3: Check for character substitution in channel name
        if self._has_character_substitution(channel_name):
            suspicious_flags.append("Potential character substitution in channel name")
            risk_score += 3.5
        
        return {
            "channel_username": channel_name,
            "channel_title": title,
            "risk_score": min(risk_score, 10.0),
            "suspicious_flags": suspicious_flags,
            "analysis_timestamp": datetime.now().isoformat(),
            "platform": "Telegram"
        }
    
    def check_username_similarity(self, suspect_username: str, vip_handles: List[str]) -> Dict:
        """Check if a username is suspiciously similar to known VIP handles"""
        similarities = {}
        max_similarity = 0.0
        closest_match = None
        
        for vip_handle in vip_handles:
            # Calculate similarity ratio
            similarity = difflib.SequenceMatcher(None, suspect_username.lower(), vip_handle.lower()).ratio()
            similarities[vip_handle] = similarity
            
            if similarity > max_similarity:
                max_similarity = similarity
                closest_match = vip_handle
        
        # Consider it suspicious if similarity is high but not exact
        is_suspicious = 0.7 <= max_similarity < 1.0
        
        return {
            "is_suspicious_similarity": is_suspicious,
            "max_similarity": max_similarity,
            "closest_vip_match": closest_match,
            "all_similarities": similarities
        }
    
    def _contains_impersonation_claims(self, text: str) -> bool:
        """Check if text contains claims of being official/verified/real"""
        impersonation_keywords = [
            "i am", "this is", "official account", "verified profile",
            "real account", "authentic", "genuine", "legitimate",
            "follow my official", "my new account", "backup account"
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in impersonation_keywords)
    
    def _has_character_substitution(self, username: str) -> bool:
        """Check if username uses character substitution tactics"""
        username_lower = username.lower()
        
        for normal_char, substitutes in self.character_substitutions.items():
            if any(sub in username_lower for sub in substitutes):
                return True
        
        return False
    
    def generate_fake_account_report(self, account_analysis: Dict, similarity_check: Dict) -> Dict:
        """Generate a comprehensive fake account report"""
        total_risk = account_analysis.get('risk_score', 0) + (similarity_check.get('max_similarity', 0) * 5)
        
        # Combine all flags
        all_flags = account_analysis.get('suspicious_flags', [])
        if similarity_check.get('is_suspicious_similarity'):
            all_flags.append(f"Username highly similar to VIP: {similarity_check.get('closest_vip_match')}")
        
        threat_level = "low"
        if total_risk >= 8.0:
            threat_level = "critical"
        elif total_risk >= 6.0:
            threat_level = "high" 
        elif total_risk >= 4.0:
            threat_level = "medium"
        
        return {
            "fake_account_risk_score": min(total_risk, 10.0),
            "threat_level": threat_level,
            "suspicious_flags": all_flags,
            "similarity_analysis": similarity_check,
            "account_details": account_analysis,
            "recommendation": self._get_recommendation(threat_level)
        }
    
    def _get_recommendation(self, threat_level: str) -> str:
        """Get recommendation based on threat level"""
        recommendations = {
            "critical": "IMMEDIATE ACTION REQUIRED - Likely impersonation account, consider legal action",
            "high": "HIGH PRIORITY - Investigate further, consider platform reporting",
            "medium": "MONITOR CLOSELY - Suspicious patterns detected, continue surveillance", 
            "low": "ROUTINE MONITORING - Low risk, continue standard monitoring"
        }
        return recommendations.get(threat_level, "Continue monitoring")