"""
NEWS SCRAPER v1.0
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

class NewsScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.cache = []
        self.cache_time = None
        self.cache_duration = 300
    
    def _get_soup(self, url, timeout=10):
        try:
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def scrape_google_news(self):
        news = []
        try:
            soup = self._get_soup('https://news.google.com/rss/search?q=gold+price+XAU+USD&hl=en-US&gl=US&ceid=US:en')
            if not soup:
                return news
            
            items = soup.find_all('item')[:12]
            for item in items:
                title_elem = item.find('title')
                pub_date = item.find('pubdate')
                source_elem = item.find('source')
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    source = source_elem.get_text(strip=True) if source_elem else 'News'
                    time_str = self._parse_time(pub_date.get_text() if pub_date else '')
                    is_gold = any(kw in title.lower() for kw in ['gold', 'xau', 'precious', 'bullion'])
                    
                    news.append({
                        'title': title,
                        'source': source,
                        'time': time_str,
                        'category': 'GOLD' if is_gold else 'FOREX'
                    })
        except Exception as e:
            print(f"Google News error: {e}")
        return news
    
    def scrape_forex_news(self):
        news = []
        try:
            soup = self._get_soup('https://news.google.com/rss/search?q=forex+USD+EUR+Fed+dollar&hl=en-US&gl=US&ceid=US:en')
            if not soup:
                return news
            
            items = soup.find_all('item')[:8]
            for item in items:
                title_elem = item.find('title')
                pub_date = item.find('pubdate')
                source_elem = item.find('source')
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    source = source_elem.get_text(strip=True) if source_elem else 'News'
                    time_str = self._parse_time(pub_date.get_text() if pub_date else '')
                    
                    news.append({
                        'title': title,
                        'source': source,
                        'time': time_str,
                        'category': 'FOREX'
                    })
        except Exception as e:
            print(f"Forex News error: {e}")
        return news
    
    def _parse_time(self, date_str):
        if not date_str:
            return ''
        try:
            for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S GMT']:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    now = datetime.now(timezone.utc)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    diff = now - dt
                    minutes = int(diff.total_seconds() / 60)
                    if minutes < 0:
                        minutes = 0
                    if minutes < 60:
                        return f"{minutes}m"
                    hours = minutes // 60
                    if hours < 24:
                        return f"{hours}h"
                    return f"{hours // 24}d"
                except:
                    continue
            return ''
        except:
            return ''
    
    def get_all_news(self, force_refresh=False):
        now = datetime.now(timezone.utc)
        
        if not force_refresh and self.cache and self.cache_time:
            cache_age = (now - self.cache_time).total_seconds()
            if cache_age < self.cache_duration:
                return self.cache
        
        all_news = []
        all_news.extend(self.scrape_google_news())
        all_news.extend(self.scrape_forex_news())
        
        seen = set()
        unique = []
        for item in all_news:
            key = item['title'][:40].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        
        unique.sort(key=lambda x: (0 if x['category'] == 'GOLD' else 1))
        
        self.cache = unique[:15]
        self.cache_time = now
        
        return self.cache


_scraper = None

def get_news_scraper():
    global _scraper
    if _scraper is None:
        _scraper = NewsScraper()
    return _scraper


if __name__ == '__main__':
    scraper = get_news_scraper()
    print("Fetching news...\n")
    news = scraper.get_all_news()
    for item in news:
        icon = "🥇" if item['category'] == 'GOLD' else "💱"
        print(f"{icon} [{item['source']}] {item['title'][:60]}... ({item['time']})")
