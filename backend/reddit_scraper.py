import requests
import json
import csv
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging
from dataclasses import dataclass, asdict
import os
import sys
import re
from collections import Counter
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging without emojis to avoid encoding issues
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('threat_monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class VIPMention:
    vip_name: str
    content: str
    title: str
    author: str
    author_karma: int
    timestamp: datetime
    platform: str
    source: str
    url: str
    score: int
    comments: int
    sentiment: str  # POSITIVE, NEUTRAL, NEGATIVE, THREATENING
    keywords_found: List[str]
    context_snippet: str
    threat_level: str
    confidence_score: float

class InteractiveVIPMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VIPMentionMonitor/2.0 (Research)',
            'Accept': 'application/json',
        })
        
        # Create monitoring directories
        self.output_dir = "vip_monitoring"
        self.mentions_dir = os.path.join(self.output_dir, "mentions")
        self.reports_dir = os.path.join(self.output_dir, "reports")
        
        for directory in [self.output_dir, self.mentions_dir, self.reports_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Predefined VIP database (expandable)
        self.vip_database = {
            'Politicians': [
                'Joe Biden', 'Donald Trump', 'Kamala Harris', 'Barack Obama', 
                'Nancy Pelosi', 'Mitch McConnell', 'Alexandria Ocasio-Cortez',
                'Narendra Modi', 'Justin Trudeau', 'Emmanuel Macron', 'Vladimir Putin'
            ],
            'Business Leaders': [
                'Elon Musk', 'Jeff Bezos', 'Bill Gates', 'Mark Zuckerberg',
                'Tim Cook', 'Satya Nadella', 'Warren Buffett', 'Sundar Pichai',
                'Jensen Huang', 'Sam Altman', 'Reed Hastings'
            ],
            'Celebrities': [
                'Taylor Swift', 'Oprah Winfrey', 'Tom Cruise', 'Leonardo DiCaprio',
                'Beyonce', 'Kim Kardashian', 'Dwayne Johnson', 'Jennifer Lawrence'
            ],
            'Tech Personalities': [
                'Mark Cuban', 'Jack Dorsey', 'Susan Wojcicki', 'Sheryl Sandberg',
                'Peter Thiel', 'Kara Swisher', 'Casey Neistat'
            ]
        }
        
        # Sentiment analysis keywords
        self.sentiment_keywords = {
            'THREATENING': [
                'kill', 'murder', 'assassinate', 'bomb', 'attack', 'destroy',
                'eliminate', 'shoot', 'gun', 'weapon', 'death', 'violence'
            ],
            'NEGATIVE': [
                'hate', 'disgusting', 'awful', 'terrible', 'horrible', 'stupid',
                'idiot', 'moron', 'corrupt', 'liar', 'fraud', 'scam', 'evil'
            ],
            'POSITIVE': [
                'love', 'amazing', 'great', 'awesome', 'brilliant', 'respect',
                'admire', 'support', 'hero', 'inspiring', 'wonderful'
            ]
        }
        
        self.rate_limit = 2
        self.monitored_vips = []
        
    def display_vip_menu(self) -> List[str]:
        """Interactive menu to select VIPs to monitor"""
        print("\n" + "="*60)
        print("           VIP SELECTION MENU")
        print("="*60)
        
        selected_vips = []
        
        while True:
            print("\nAvailable VIP Categories:")
            categories = list(self.vip_database.keys())
            
            for i, category in enumerate(categories, 1):
                print(f"{i}. {category} ({len(self.vip_database[category])} people)")
            
            print(f"{len(categories) + 1}. Add Custom VIP")
            print(f"{len(categories) + 2}. Show Selected VIPs ({len(selected_vips)})")
            print(f"{len(categories) + 3}. Start Monitoring")
            print("0. Exit")
            
            try:
                choice = int(input("\nSelect option: "))
                
                if choice == 0:
                    sys.exit(0)
                elif choice == len(categories) + 3:  # Start monitoring
                    if selected_vips:
                        break
                    else:
                        print("Please select at least one VIP first!")
                elif choice == len(categories) + 2:  # Show selected
                    if selected_vips:
                        print(f"\nSelected VIPs ({len(selected_vips)}):")
                        for i, vip in enumerate(selected_vips, 1):
                            print(f"  {i}. {vip}")
                    else:
                        print("\nNo VIPs selected yet.")
                elif choice == len(categories) + 1:  # Add custom
                    custom_vip = input("Enter custom VIP name: ").strip()
                    if custom_vip and custom_vip not in selected_vips:
                        selected_vips.append(custom_vip)
                        print(f"Added '{custom_vip}' to monitoring list!")
                elif 1 <= choice <= len(categories):
                    category = categories[choice - 1]
                    self.display_category_menu(category, selected_vips)
                else:
                    print("Invalid choice!")
                    
            except ValueError:
                print("Please enter a valid number!")
        
        self.monitored_vips = selected_vips
        return selected_vips
    
    def display_category_menu(self, category: str, selected_vips: List[str]):
        """Display VIPs in a category for selection"""
        vips = self.vip_database[category]
        
        print(f"\n{category} VIPs:")
        for i, vip in enumerate(vips, 1):
            status = "[SELECTED]" if vip in selected_vips else ""
            print(f"{i:2d}. {vip} {status}")
        
        print(f"{len(vips) + 1}. Select All")
        print(f"{len(vips) + 2}. Back to Main Menu")
        
        try:
            choice = int(input(f"\nSelect {category} VIP (or option): "))
            
            if choice == len(vips) + 2:  # Back
                return
            elif choice == len(vips) + 1:  # Select all
                for vip in vips:
                    if vip not in selected_vips:
                        selected_vips.append(vip)
                print(f"Added all {category} VIPs!")
            elif 1 <= choice <= len(vips):
                vip = vips[choice - 1]
                if vip not in selected_vips:
                    selected_vips.append(vip)
                    print(f"Added '{vip}' to monitoring list!")
                else:
                    selected_vips.remove(vip)
                    print(f"Removed '{vip}' from monitoring list!")
            else:
                print("Invalid choice!")
                
        except ValueError:
            print("Please enter a valid number!")
    
    def analyze_sentiment(self, text: str, title: str = "") -> Dict:
        """Analyze sentiment and threat level of text"""
        combined_text = f"{title} {text}".lower()
        
        sentiment = "NEUTRAL"
        keywords_found = []
        confidence = 0.0
        threat_level = "LOW"
        
        # Check for threatening language
        threatening_matches = [kw for kw in self.sentiment_keywords['THREATENING'] if kw in combined_text]
        if threatening_matches:
            sentiment = "THREATENING"
            threat_level = "CRITICAL"
            keywords_found.extend(threatening_matches)
            confidence = 0.9
        
        # Check for negative sentiment
        negative_matches = [kw for kw in self.sentiment_keywords['NEGATIVE'] if kw in combined_text]
        if negative_matches and sentiment != "THREATENING":
            sentiment = "NEGATIVE"
            threat_level = "MEDIUM" if len(negative_matches) > 2 else "LOW"
            keywords_found.extend(negative_matches)
            confidence = 0.6
        
        # Check for positive sentiment
        positive_matches = [kw for kw in self.sentiment_keywords['POSITIVE'] if kw in combined_text]
        if positive_matches and sentiment == "NEUTRAL":
            sentiment = "POSITIVE"
            keywords_found.extend(positive_matches)
            confidence = 0.5
        
        return {
            'sentiment': sentiment,
            'threat_level': threat_level,
            'keywords_found': keywords_found,
            'confidence_score': round(confidence, 2)
        }
    
    def search_vip_mentions(self, vip_name: str, subreddits: List[str], limit: int = 50) -> List[VIPMention]:
        """Search for specific VIP mentions across subreddits"""
        mentions = []
        vip_variations = self.get_vip_variations(vip_name)
        
        print(f"\nSearching for mentions of: {vip_name}")
        print(f"Variations: {', '.join(vip_variations[:3])}{'...' if len(vip_variations) > 3 else ''}")
        
        for subreddit in subreddits:
            try:
                print(f"  -> Checking r/{subreddit}")
                
                # Search recent posts
                url = f"https://www.reddit.com/r/{subreddit}/new.json"
                params = {'limit': limit, 'raw_json': 1}
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                for item in data['data']['children']:
                    post = item['data']
                    title = post.get('title', '').lower()
                    content = post.get('selftext', '').lower()
                    combined_text = f"{title} {content}"
                    
                    # Check if any VIP variation is mentioned
                    if any(variation.lower() in combined_text for variation in vip_variations):
                        # Analyze sentiment
                        analysis = self.analyze_sentiment(content, title)
                        
                        # Extract context snippet around VIP mention
                        context = self.extract_context_snippet(combined_text, vip_variations)
                        
                        mention = VIPMention(
                            vip_name=vip_name,
                            content=post.get('selftext', '')[:500],
                            title=post.get('title', ''),
                            author=post.get('author', '[deleted]'),
                            author_karma=post.get('author_flair_text', 'Unknown'),
                            timestamp=datetime.fromtimestamp(post.get('created_utc', 0)),
                            platform="Reddit",
                            source=f"r/{subreddit}",
                            url=f"https://www.reddit.com{post.get('permalink', '')}",
                            score=int(post.get('score', 0)),
                            comments=int(post.get('num_comments', 0)),
                            sentiment=analysis['sentiment'],
                            keywords_found=analysis['keywords_found'],
                            context_snippet=context,
                            threat_level=analysis['threat_level'],
                            confidence_score=analysis['confidence_score']
                        )
                        mentions.append(mention)
                
                time.sleep(self.rate_limit)
                
            except Exception as e:
                print(f"    Error checking r/{subreddit}: {e}")
        
        return mentions
    
    def get_vip_variations(self, vip_name: str) -> List[str]:
        """Get different variations of VIP name for better matching"""
        variations = [vip_name]
        
        # Add common variations
        if ' ' in vip_name:
            # First name only
            variations.append(vip_name.split()[0])
            # Last name only  
            variations.append(vip_name.split()[-1])
            # Reversed order
            parts = vip_name.split()
            if len(parts) == 2:
                variations.append(f"{parts[1]} {parts[0]}")
        
        # Add @username style
        variations.append(f"@{vip_name.replace(' ', '')}")
        
        return variations
    
    def extract_context_snippet(self, text: str, vip_variations: List[str]) -> str:
        """Extract context around VIP mention"""
        for variation in vip_variations:
            if variation.lower() in text:
                # Find position of mention
                pos = text.lower().find(variation.lower())
                # Extract context (50 chars before and after)
                start = max(0, pos - 50)
                end = min(len(text), pos + len(variation) + 50)
                snippet = text[start:end].strip()
                return f"...{snippet}..." if start > 0 or end < len(text) else snippet
        return text[:100] + "..." if len(text) > 100 else text
    
    def monitor_selected_vips(self, subreddits: List[str], posts_per_sub: int = 25) -> Dict[str, List[VIPMention]]:
        """Monitor all selected VIPs across specified subreddits"""
        all_mentions = {}
        
        print(f"\nStarting monitoring for {len(self.monitored_vips)} VIPs...")
        print(f"Subreddits: {', '.join(subreddits)}")
        print(f"Posts per subreddit: {posts_per_sub}")
        print("-" * 60)
        
        for vip in self.monitored_vips:
            mentions = self.search_vip_mentions(vip, subreddits, posts_per_sub)
            all_mentions[vip] = mentions
            print(f"  Found {len(mentions)} mentions of {vip}")
        
        return all_mentions
    
    def generate_vip_report(self, all_mentions: Dict[str, List[VIPMention]]) -> str:
        """Generate comprehensive VIP mention report"""
        report = []
        report.append("=" * 70)
        report.append("         VIP MENTION MONITORING REPORT")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Monitored VIPs: {len(all_mentions)}")
        
        total_mentions = sum(len(mentions) for mentions in all_mentions.values())
        report.append(f"Total Mentions Found: {total_mentions}")
        report.append("")
        
        # Summary by VIP
        report.append("MENTIONS BY VIP:")
        report.append("-" * 40)
        for vip, mentions in all_mentions.items():
            if mentions:
                threat_count = sum(1 for m in mentions if m.threat_level in ['HIGH', 'CRITICAL'])
                report.append(f"{vip}: {len(mentions)} mentions ({threat_count} threats)")
            else:
                report.append(f"{vip}: No mentions found")
        report.append("")
        
        # Critical/High threat mentions
        critical_mentions = []
        for vip, mentions in all_mentions.items():
            for mention in mentions:
                if mention.threat_level in ['CRITICAL', 'HIGH']:
                    critical_mentions.append((vip, mention))
        
        if critical_mentions:
            report.append("CRITICAL/HIGH THREAT MENTIONS:")
            report.append("-" * 40)
            for vip, mention in critical_mentions[:10]:  # Top 10
                report.append(f"\nVIP: {vip}")
                report.append(f"Threat Level: {mention.threat_level} ({mention.sentiment})")
                report.append(f"Author: {mention.author}")
                report.append(f"Source: {mention.source}")
                report.append(f"Context: {mention.context_snippet}")
                report.append(f"URL: {mention.url}")
                report.append(f"Keywords: {', '.join(mention.keywords_found[:5])}")
        
        # Top active authors mentioning VIPs
        all_authors = []
        for mentions in all_mentions.values():
            all_authors.extend([m.author for m in mentions if m.author != '[deleted]'])
        
        if all_authors:
            author_counts = Counter(all_authors).most_common(10)
            report.append(f"\nTOP AUTHORS MENTIONING VIPS:")
            report.append("-" * 40)
            for author, count in author_counts:
                report.append(f"{author}: {count} mentions")
        
        return "\n".join(report)
    
    def export_mentions(self, all_mentions: Dict[str, List[VIPMention]], format_type: str = "json") -> str:
        """Export VIP mentions to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type.lower() == "json":
            filename = f"vip_mentions_{timestamp}.json"
            filepath = os.path.join(self.mentions_dir, filename)
            
            export_data = {}
            for vip, mentions in all_mentions.items():
                export_data[vip] = []
                for mention in mentions:
                    mention_dict = asdict(mention)
                    mention_dict['timestamp'] = mention_dict['timestamp'].isoformat()
                    export_data[vip].append(mention_dict)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        elif format_type.lower() == "csv":
            filename = f"vip_mentions_{timestamp}.csv"
            filepath = os.path.join(self.mentions_dir, filename)
            
            all_mention_list = []
            for vip, mentions in all_mentions.items():
                all_mention_list.extend(mentions)
            
            if all_mention_list:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=asdict(all_mention_list[0]).keys())
                    writer.writeheader()
                    for mention in all_mention_list:
                        mention_dict = asdict(mention)
                        mention_dict['timestamp'] = mention_dict['timestamp'].isoformat()
                        mention_dict['keywords_found'] = '; '.join(mention_dict['keywords_found'])
                        writer.writerow(mention_dict)
        
        print(f"Data exported to: {filepath}")
        return filepath

def main():
    """Interactive VIP Monitoring System"""
    print("=" * 70)
    print("     INTERACTIVE VIP THREAT & MENTION MONITORING SYSTEM")
    print("=" * 70)
    print("Track what people are saying about specific VIPs online!")
    print()
    
    monitor = InteractiveVIPMonitor()
    
    try:
        # Interactive VIP selection
        selected_vips = monitor.display_vip_menu()
        
        print(f"\nMonitoring {len(selected_vips)} VIPs:")
        for i, vip in enumerate(selected_vips, 1):
            print(f"  {i}. {vip}")
        
        # Configure monitoring
        print(f"\nConfiguring monitoring parameters...")
        
        # Default subreddits (user can modify)
        subreddits = ['politics', 'worldnews', 'news', 'technology', 'business', 'entertainment']
        posts_per_sub = 30
        
        print(f"Subreddits to monitor: {', '.join(subreddits)}")
        print(f"Posts per subreddit: {posts_per_sub}")
        
        # Start monitoring
        print("\nStarting VIP mention monitoring...")
        all_mentions = monitor.monitor_selected_vips(subreddits, posts_per_sub)
        
        # Display results
        print("\n" + "="*60)
        print("MONITORING RESULTS")
        print("="*60)
        
        total_found = 0
        for vip, mentions in all_mentions.items():
            print(f"\n{vip}: {len(mentions)} mentions")
            
            if mentions:
                total_found += len(mentions)
                # Show top 3 mentions for each VIP
                for i, mention in enumerate(mentions[:3], 1):
                    sentiment_emoji = {
                        'POSITIVE': '+', 'NEGATIVE': '-', 
                        'THREATENING': '!!!', 'NEUTRAL': '~'
                    }.get(mention.sentiment, '?')
                    
                    print(f"  {i}. [{sentiment_emoji}] by {mention.author} in {mention.source}")
                    print(f"     \"{mention.context_snippet[:80]}...\"")
                    print(f"     Score: {mention.score}, Comments: {mention.comments}")
                
                if len(mentions) > 3:
                    print(f"     ... and {len(mentions) - 3} more mentions")
        
        if total_found > 0:
            # Generate report
            report = monitor.generate_vip_report(all_mentions)
            print(f"\n{report}")
            
            # Export data
            json_file = monitor.export_mentions(all_mentions, "json")
            csv_file = monitor.export_mentions(all_mentions, "csv")
            
            # Save report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(monitor.reports_dir, f"vip_report_{timestamp}.txt")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"\nFiles saved:")
            print(f"  Report: {report_file}")
            print(f"  JSON data: {json_file}")
            print(f"  CSV data: {csv_file}")
        else:
            print("\nNo mentions found for selected VIPs in recent posts.")
        
        print(f"\nMonitoring complete! Total mentions found: {total_found}")
        print("Check the exported files for detailed analysis.")
        
    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()