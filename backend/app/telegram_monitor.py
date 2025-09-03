# backend/app/telegram_monitor.py
import requests
import time
import json
from datetime import datetime
from typing import List, Dict, Optional
from .fake_account_detector import FakeAccountDetector

class TelegramMonitor:
    """Monitors Telegram channels for VIP mentions and fake accounts"""
    
    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or self._get_bot_token()
        self.fake_detector = FakeAccountDetector()
        self.monitored_channels = self._load_monitored_channels()
        self.last_message_ids = {}  # Track last processed message per channel
        
    def _get_bot_token(self) -> Optional[str]:
        """Get bot token from environment or config"""
        import os
        return os.getenv("TELEGRAM_MONITOR_BOT_TOKEN")
    
    def _load_monitored_channels(self) -> List[str]:
        """Load list of channels to monitor - can be expanded to read from config"""
        return [
            "@breakingnews", 
            "@worldnews",
            "@politicsnews", 
            "@technews",
            "@cryptonews",
            # Add more public channels that might mention VIPs
        ]
    
    def add_channel_to_monitor(self, channel_username: str):
        """Add a new channel to monitoring list"""
        if channel_username not in self.monitored_channels:
            self.monitored_channels.append(channel_username)
            print(f"Added {channel_username} to monitoring list")
    
    def get_channel_info(self, channel_username: str) -> Optional[Dict]:
        """Get channel information using Telegram Bot API"""
        if not self.bot_token:
            print("No Telegram bot token available for channel info")
            return None
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getChat"
            params = {"chat_id": channel_username}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return data["result"]
            
            print(f"Could not get info for channel {channel_username}")
            return None
            
        except Exception as e:
            print(f"Error getting channel info for {channel_username}: {e}")
            return None
    
    def search_telegram_web(self, vip_name: str, channel_username: str) -> List[Dict]:
        """
        Fallback method: Search Telegram using web scraping approach
        This is used when Bot API access is limited
        """
        found_mentions = []
        
        try:
            # Use Telegram's web interface (t.me) for public channels
            channel_clean = channel_username.replace("@", "")
            search_url = f"https://t.me/s/{channel_clean}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # Simple text search in the HTML response
                content = response.text.lower()
                vip_variations = self._get_vip_variations(vip_name)
                
                for variation in vip_variations:
                    if variation.lower() in content:
                        # Found a potential mention
                        found_mentions.append({
                            "channel": channel_username,
                            "vip_mentioned": vip_name,
                            "variation_found": variation,
                            "search_url": search_url,
                            "timestamp": datetime.now().isoformat(),
                            "method": "web_scrape"
                        })
                        break
                        
        except Exception as e:
            print(f"Error in web search for {channel_username}: {e}")
        
        return found_mentions
    
    def monitor_channel_for_vip(self, vip_name: str, channel_username: str) -> List[Dict]:
        """Monitor a specific channel for mentions of a VIP"""
        mentions_found = []
        
        # First, try to get channel info for fake account analysis
        channel_info = self.get_channel_info(channel_username)
        
        if channel_info:
            # Analyze the channel itself for suspicious characteristics
            channel_analysis = self.fake_detector.analyze_telegram_account(channel_info)
            
            # If channel is suspicious, flag it
            if channel_analysis.get("risk_score", 0) > 5.0:
                mentions_found.append({
                    "type": "suspicious_channel",
                    "channel": channel_username,
                    "vip_target": vip_name,
                    "fake_account_analysis": channel_analysis,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Search for actual mentions in the channel
        web_mentions = self.search_telegram_web(vip_name, channel_username)
        mentions_found.extend(web_mentions)
        
        return mentions_found
    
    def scan_all_channels_for_vip(self, vip_name: str) -> List[Dict]:
        """Scan all monitored channels for a specific VIP"""
        all_mentions = []
        
        print(f"Scanning {len(self.monitored_channels)} Telegram channels for {vip_name}")
        
        for channel in self.monitored_channels:
            try:
                mentions = self.monitor_channel_for_vip(vip_name, channel)
                all_mentions.extend(mentions)
                
                # Be respectful to Telegram's rate limits
                time.sleep(2)
                
            except Exception as e:
                print(f"Error monitoring channel {channel} for {vip_name}: {e}")
                continue
        
        return all_mentions
    
    def _get_vip_variations(self, vip_name: str) -> List[str]:
        """Generate variations of VIP name for better detection"""
        variations = [vip_name]
        
        # Add common variations
        if ' ' in vip_name:
            # Add first name only
            variations.append(vip_name.split()[0])
            # Add last name only  
            variations.append(vip_name.split()[-1])
            # Add with underscores
            variations.append(vip_name.replace(' ', '_'))
            # Add with dots
            variations.append(vip_name.replace(' ', '.'))
        
        # Add @mention style
        variations.append(f"@{vip_name.replace(' ', '')}")
        
        return variations
    
    def detect_impersonation_channels(self, vip_handles: List[str]) -> List[Dict]:
        """Actively search for channels that might be impersonating VIPs"""
        suspicious_channels = []
        
        print("Searching for potential impersonation channels...")
        
        for vip_handle in vip_handles:
            # Generate potential impersonation channel names
            potential_fake_names = self._generate_fake_channel_names(vip_handle)
            
            for fake_name in potential_fake_names:
                try:
                    channel_info = self.get_channel_info(f"@{fake_name}")
                    
                    if channel_info:
                        # Analyze for impersonation
                        fake_analysis = self.fake_detector.analyze_telegram_account(channel_info)
                        similarity_check = self.fake_detector.check_username_similarity(
                            fake_name, vip_handles
                        )
                        
                        # Generate comprehensive report
                        full_report = self.fake_detector.generate_fake_account_report(
                            fake_analysis, similarity_check
                        )
                        
                        if full_report.get("fake_account_risk_score", 0) > 4.0:
                            suspicious_channels.append({
                                "channel_username": fake_name,
                                "target_vip": vip_handle,
                                "impersonation_analysis": full_report,
                                "channel_info": channel_info,
                                "detection_timestamp": datetime.now().isoformat()
                            })
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    print(f"Error checking potential fake channel @{fake_name}: {e}")
                    continue
        
        return suspicious_channels
    
    def _generate_fake_channel_names(self, vip_handle: str) -> List[str]:
        """Generate potential fake channel names based on VIP handle"""
        fake_names = []
        base_name = vip_handle.lower().replace(' ', '')
        
        # Common impersonation patterns
        variations = [
            f"{base_name}official",
            f"{base_name}_official", 
            f"real{base_name}",
            f"{base_name}verified",
            f"{base_name}news",
            f"{base_name}updates",
            f"official{base_name}",
            f"{base_name}real",
            f"{base_name}authentic"
        ]
        
        # Character substitution variations
        char_subs = {
            'o': '0', 'i': '1', 'l': '1', 'e': '3', 'a': '@'
        }
        
        for char, replacement in char_subs.items():
            if char in base_name:
                fake_names.append(base_name.replace(char, replacement))
        
        fake_names.extend(variations)
        return list(set(fake_names))  # Remove duplicates
    
    def process_telegram_mentions(self, mentions: List[Dict], vip_name: str) -> List[Dict]:
        """Process found mentions and send to analysis API"""
        processed_results = []
        
        for mention in mentions:
            try:
                if mention.get("type") == "suspicious_channel":
                    # Handle suspicious channel detection
                    api_payload = {
                        "twitter_handle": vip_name,
                        "text_to_check": f"Suspicious Telegram channel detected: @{mention['channel']}. "
                                       f"Risk factors: {', '.join(mention['fake_account_analysis']['suspicious_flags'])}",
                        "platform": "Telegram",
                        "source_url": f"https://t.me/{mention['channel'].replace('@', '')}",
                        "fake_account_analysis": mention.get("fake_account_analysis")
                    }
                else:
                    # Handle content mention
                    api_payload = {
                        "twitter_handle": vip_name,
                        "text_to_check": f"VIP mentioned in Telegram channel {mention.get('channel')}. "
                                       f"Variation found: {mention.get('variation_found')}",
                        "platform": "Telegram", 
                        "source_url": mention.get("search_url")
                    }
                
                # Send to main analysis API
                response = requests.post(
                    "http://localhost:8000/analyze/threat", 
                    json=api_payload,
                    timeout=30
                )
                
                processed_results.append({
                    "mention": mention,
                    "api_response": response.status_code,
                    "processed_at": datetime.now().isoformat()
                })
                
            except Exception as e:
                print(f"Error processing Telegram mention: {e}")
                processed_results.append({
                    "mention": mention,
                    "error": str(e),
                    "processed_at": datetime.now().isoformat()
                })
        
        return processed_results