# In backend/app/scanner.py
import requests
import time
import os
import chromadb # To find which VIPs to monitor
from .fake_account_detector import FakeAccountDetector # Import the detector

# --- Keep these helper functions from your scraper ---
def get_vip_variations(vip_name: str) -> list[str]:
    # ... (copy the exact code from your scraper)
    variations = [vip_name]
    if ' ' in vip_name:
        variations.append(vip_name.split()[0])
        variations.append(vip_name.split()[-1])
    return variations

# --- This is the core refactored function ---
def scan_reddit_for_mentions(vip_name: str, subreddits: list[str]):
    """Scans subreddits and sends any found mentions to the main analysis API."""
    print(f"[*] Scanning Reddit for mentions of: {vip_name}")
    session = requests.Session()
    session.headers.update({'User-Agent': 'VIPGuardianScanner/1.0'})
    vip_variations = get_vip_variations(vip_name)
    
    # Instantiate the detector once per scan session
    fake_detector = FakeAccountDetector()

    for subreddit in subreddits:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=25"
            response = session.get(url)
            response.raise_for_status()
            data = response.json()

            for item in data['data']['children']:
                post = item['data']
                title = post.get('title', '')
                content = post.get('selftext', '')
                full_text = f"{title}\n{content}"

                if any(variation.lower() in full_text.lower() for variation in vip_variations):
                    post_url = f"https://www.reddit.com{post.get('permalink', '')}"
                    print(f"  [!] Found potential mention of {vip_name} in r/{subreddit}: {post_url}")

                    # --- INTEGRATION: Analyze the Reddit account ---
                    author = post.get('author')
                    fake_account_analysis = fake_detector.analyze_reddit_account(author, post)
                    if fake_account_analysis['risk_score'] > 3.0:
                         print(f"    [!] High-risk Reddit account detected: @{author} (Score: {fake_account_analysis['risk_score']})")


                    # This is the key change: Call our own API for analysis!
                    api_payload = {
                        "twitter_handle": vip_name, # The VIP's identifier
                        "text_to_check": full_text,
                        "platform": "Reddit",
                        "source_url": post_url,
                        "fake_account_analysis": fake_account_analysis # Add the analysis to the payload
                    }
                    
                    try:
                        # Send to our powerful analysis engine
                        requests.post("http://localhost:8000/analyze/threat", json=api_payload, timeout=20)
                    except Exception as api_err:
                        print(f"    [-] ERROR: Could not send mention to analysis API: {api_err}")

            time.sleep(2) # Be respectful to Reddit's API
        except Exception as e:
            print(f"  [-] ERROR scanning r/{subreddit}: {e}")

def run_continuous_scan():
    """The main loop for the scanner background task."""
    chroma_client = chromadb.PersistentClient(path="./db")
    subreddits_to_scan = ['politics', 'worldnews', 'news', 'technology', 'conspiracy', 'finance']
    
    while True:
        print("\n--- Starting new Reddit scanner cycle ---")
        # Automatically discover which VIPs to monitor by checking the database
        collections = chroma_client.list_collections()
        monitored_vips = [col.name.replace("vip_", "") for col in collections]

        if not monitored_vips:
            print("[Scanner] No VIP twins found in the database. Waiting...")
        else:
            print(f"[Scanner] Monitoring {len(monitored_vips)} VIPs on Reddit: {', '.join(monitored_vips)}")
            for vip in monitored_vips:
                scan_reddit_for_mentions(vip, subreddits_to_scan)

        print(f"--- Reddit scanner cycle complete. Waiting for 10 minutes... ---")
        time.sleep(600) # Wait for 10 minutes before the next cycle
