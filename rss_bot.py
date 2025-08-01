import feedparser
import requests
import json
import os
import re
from datetime import datetime, timedelta
import hashlib

class MultiChannelCyberSecBot:
    def __init__(self):
        # Get all webhook URLs from environment variables
        self.webhooks = {
            'cryptography': os.getenv('CRYPTO_WEBHOOK_URL'),
            'mobile_security': os.getenv('MOBILE_WEBHOOK_URL'),
            'web_security': os.getenv('WEB_WEBHOOK_URL'),
            'digital_forensics': os.getenv('FORENSICS_WEBHOOK_URL'),
            'osint': os.getenv('OSINT_WEBHOOK_URL'),
            'matlab': os.getenv('MATLAB_WEBHOOK_URL'),
            'writeups': os.getenv('WRITEUPS_WEBHOOK_URL'),
            'ctf': os.getenv('CTF_WEBHOOK_URL')
        }
        
        # Remove None values (webhooks not configured)
        self.webhooks = {k: v for k, v in self.webhooks.items() if v}
        
        # Track posted items to prevent duplicates
        self.posted_items = set()
        
        # RSS feeds organized by category and difficulty
        self.feeds = {
            'cryptography': [
                'https://blog.cryptographyengineering.com/feed/',
                'https://eprint.iacr.org/rss/rss.xml'
            ],
            'mobile_security': [
                'https://blog.zimperium.com/feed/',
                'https://www.nowsecure.com/blog/feed/'
            ],
            'web_security': [
                'https://portswigger.net/blog/rss',
                'https://blog.detectify.com/feed/'
            ],
            'digital_forensics': [
                'https://forensicfocus.com/feed/',
            ],
            'osint': [
                'https://www.bellingcat.com/feed/',
                'https://inteltechniques.com/blog/feed/'
            ],
            'writeups': [
                'https://0x00sec.org/latest.rss',  # Mixed difficulty writeups
                'https://www.exploit-db.com/rss.xml',  # Exploit writeups
            ],
            'ctf': [
                'https://ctftime.org/event/list/upcoming/rss/',  # CTF events and announcements
            ]
        }
        
        # Keywords to help classify content difficulty
        self.beginner_keywords = [
            'beginner', 'intro', 'introduction', 'basics', 'fundamentals', 
            'getting started', 'tutorial', 'guide', '101', 'basic'
        ]
        
        self.intermediate_keywords = [
            'advanced', 'intermediate', 'deep dive', 'exploitation', 'bypass',
            'analysis', 'reverse engineering', 'advanced techniques'
        ]
    
    def classify_difficulty(self, title, description):
        """Determine if content is beginner or intermediate based on keywords"""
        text = f"{title} {description}".lower()
        
        beginner_score = sum(1 for keyword in self.beginner_keywords if keyword in text)
        intermediate_score = sum(1 for keyword in self.intermediate_keywords if keyword in text)
        
        if beginner_score > intermediate_score:
            return 'beginner'
        elif intermediate_score > 0:
            return 'intermediate'
        else:
            return 'general'  # Default to general category
    
    def get_appropriate_channel(self, category, title, description):
        """Determine which channel to post to based on content"""
        difficulty = self.classify_difficulty(title, description)
        
        # Handle writeups
        if any(keyword in title.lower() or keyword in description.lower() 
               for keyword in ['writeup', 'write-up', 'walkthrough', 'solution']):
            return 'writeups'
        
        # Handle CTF content
        if any(keyword in title.lower() or keyword in description.lower() 
               for keyword in ['ctf', 'capture the flag', 'competition', 'challenge']):
            return 'ctf'
        
        # Default to main category
        return category
    
    def generate_item_id(self, title, link):
        """Create unique ID for each article to prevent duplicates"""
        return hashlib.md5(f"{title}{link}".encode()).hexdigest()
    
    def send_to_discord(self, channel, title, description, url, category):
        """Send formatted message to specific Discord channel"""
        webhook_url = self.webhooks.get(channel)
        if not webhook_url:
            print(f"⚠️  No webhook configured for channel: {channel}")
            return False
        
        # Color coding by category
        colors = {
            'cryptography': 0x9932CC,
            'mobile_security': 0xFF6347,
            'web_security': 0x1E90FF,
            'digital_forensics': 0xFF4500,
            'osint': 0x20B2AA,
            'matlab': 0x0076A8,
            'writeups': 0x32CD32,
            'ctf': 0xFF1493
        }
        
        # Emojis for different categories
        emojis = {
            'cryptography': '🔐',
            'mobile_security': '📱',
            'web_security': '🌐',
            'digital_forensics': '🔍',
            'osint': '🕵️',
            'matlab': '📊',
            'writeups': '📝',
            'ctf': '🚩'
        }
        
        embed = {
            "title": title[:256],  # Discord title limit
            "description": description[:2048] if description else "No description available",
            "url": url,
            "color": colors.get(channel, 0x808080),
            "footer": {
                "text": f"{emojis.get(channel, '📡')} {channel.replace('_', ' ').title()}"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        data = {
            "embeds": [embed],
            "username": "🔐 CyberSec Intel Hub"
        }
        
        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            if response.status_code == 204:
                print(f"✅ Posted to #{channel}: {title[:40]}...")
                return True
            else:
                print(f"❌ Discord error for #{channel} ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            print(f"❌ Network error for #{channel}: {e}")
            return False
    
    def check_single_feed(self, feed_url, base_category, max_items=5):
        """Check one RSS feed and route content to appropriate channels"""
        try:
            print(f"🔍 Checking {base_category}: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                print(f"⚠️  No entries found in {feed_url}")
                return
                
            new_items = 0
            for entry in feed.entries[:max_items]:
                item_id = self.generate_item_id(entry.title, entry.link)
                
                # Skip if already posted
                if item_id in self.posted_items:
                    continue
                
                # Check if item is recent (last 48 hours)
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                        if pub_date < datetime.now() - timedelta(hours=48):
                            continue
                except:
                    pass
                
                # Determine appropriate channel
                target_channel = self.get_appropriate_channel(
                    base_category, 
                    entry.title, 
                    getattr(entry, 'summary', '')
                )
                
                # Send to Discord
                success = self.send_to_discord(
                    channel=target_channel,
                    title=entry.title,
                    description=getattr(entry, 'summary', ''),
                    url=entry.link,
                    category=base_category
                )
                
                if success:
                    self.posted_items.add(item_id)
                    new_items += 1
                
                # Rate limiting
                if new_items >= 2:  # Max 2 items per feed per run
                    break
                    
        except Exception as e:
            print(f"❌ Error processing {feed_url}: {e}")
    
    def run(self):
        """Main function to check all feeds"""
        print(f"🚀 Starting multi-channel RSS check at {datetime.now()}")
        print(f"📡 Configured channels: {', '.join(self.webhooks.keys())}")
        
        for category, feed_urls in self.feeds.items():
            for feed_url in feed_urls:
                self.check_single_feed(feed_url, category)
                # Small delay between feeds
                import time
                time.sleep(2)
        
        print(f"✅ Multi-channel RSS check complete!")

# Entry point for GitHub Actions
if __name__ == "__main__":
    bot = MultiChannelCyberSecBot()
    bot.run()
