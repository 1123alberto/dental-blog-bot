import feedparser
import time

import requests
from bs4 import BeautifulSoup

FEEDS = [
    "https://www.dentistrytoday.com/feed/",
    "https://bmcoralhealth.biomedcentral.com/articles/most-recent/rss.xml",
    "https://www.dentistryiq.com/rss",
    "https://www.sciencedaily.com/rss/health_medicine/dentistry.xml",
    "https://www.dental-tribune.com/news/feed/",
    "https://www.beckersdental.com/feed/",
]


def fetch_dental_news():
    articles = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })

    for url in FEEDS:
        print(f"Fetching from {url}...")
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:  # Get latest 5 from each
            image_url = None

            # 1. Try to find image in media content
            if "media_content" in entry and len(entry.media_content) > 0:
                image_url = entry.media_content[0]["url"]
            # 2. Try enclosures
            elif "enclosures" in entry and len(entry.enclosures) > 0:
                for enc in entry.enclosures:
                    if enc.get("type", "").startswith("image/"):
                        image_url = enc.get("url")
                        break
            # 3. Try parsing HTML fields (summary, description, content) for <img> tag
            if not image_url or "bacteria-on-tooth-surface.webp" in image_url:
                image_url = None # Reset if it was the generic one
                html_fields = [
                    entry.get("summary", ""),
                    entry.get("description", ""),
                ]
                if "content" in entry:
                    for c in entry.content:
                        html_fields.append(c.get("value", ""))

                for html_content in html_fields:
                    if not html_content:
                        continue
                    soup = BeautifulSoup(html_content, features="html.parser")
                    img_tag = soup.find("img")
                    if img_tag:
                        image_url = img_tag.get("src")
                        if image_url:
                            break

            # 4. Fallback: Fetch the actual article page and look for meta images
            if not image_url and entry.link:
                try:
                    resp = session.get(entry.link, timeout=5)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, features="html.parser")
                        # Look for OpenGraph image
                        og_img = soup.find("meta", property="og:image")
                        if og_img and og_img.get("content"):
                            image_url = og_img.get("content")
                        # Look for Twitter image
                        if not image_url:
                            tw_img = soup.find("meta", name="twitter:image")
                            if tw_img and tw_img.get("content"):
                                image_url = tw_img.get("content")
                        # Look for first large image if still nothing
                        if not image_url:
                            # This is a bit risky but can work as a last resort
                            for img in soup.find_all("img"):
                                src = img.get("src")
                                if src and src.startswith("http") and not any(x in src.lower() for x in ["icon", "logo", "avatar", "ads"]):
                                    image_url = src
                                    break
                except Exception as e:
                    print(f"Error fetching article page for image: {e}")

            articles.append(
                {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": clean_html(
                        entry.get("summary", entry.get("description", ""))
                    ),
                    "image": image_url,
                    "source": feed.feed.get("title", "Dental Journal"),
                    "date": time.strftime("%b %d, %Y", entry.published_parsed) if entry.get("published_parsed") else entry.get("published", "Recently"),
                }
            )
    return articles


def clean_html(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, features="html.parser")
    return soup.get_text()


if __name__ == "__main__":
    news = fetch_dental_news()
    for item in news:
        print(f"Title: {item['title']}")
        print(f"Image: {item['image']}")
        print("-" * 20)
