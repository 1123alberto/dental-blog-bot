import feedparser
import time
import re

import requests
from bs4 import BeautifulSoup

FEEDS = [
    "https://www.dentistrytoday.com/feed/",
    "https://www.dental-tribune.com/news/feed/",
    "https://www.beckersdental.com/feed/",
    "https://newdentistblog.ada.org/feed",
    "https://www.dentalhealth.org/Handlers/Rss.ashx?ID=2074",
    "https://onlinelibrary.wiley.com/feed/1600051x/most-recent",
    "https://onlinelibrary.wiley.com/feed/16000501/most-recent",
]


def extract_article_content_and_image(session, url):
    """
    Fetches the article URL and extracts the main text content and featured image.
    """
    text_content = ""
    image_url = None
    if not url:
        return text_content, image_url

    try:
        resp = session.get(url, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, features="html.parser")
            
            # --- Extract Image ---
            # 1. Look for OpenGraph image
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                image_url = og_img.get("content")
            # 2. Look for Twitter image
            if not image_url:
                tw_img = soup.find("meta", name="twitter:image")
                if tw_img and tw_img.get("content"):
                    image_url = tw_img.get("content")
            # 3. Look for first large image if still nothing
            if not image_url:
                for img in soup.find_all("img"):
                    src = img.get("src")
                    if src and src.startswith("http") and not any(x in src.lower() for x in ["icon", "logo", "avatar", "ads"]):
                        image_url = src
                        break

            # --- Extract Main Text ---
            # Remove boilerplate elements
            for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "noscript", "iframe"]):
                tag.decompose()
            
            # Find the main container
            main_container = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile("article|content|body", re.I)) or soup.body
            
            if main_container:
                paragraphs = main_container.find_all("p")
                valid_paras = []
                for p in paragraphs:
                    txt = p.get_text().strip()
                    # Skip very short paragraphs or boilerplate terms
                    if len(txt.split()) > 10 and not any(term in txt.lower() for term in ["cookie", "privacy policy", "terms of service", "newsletter"]):
                        valid_paras.append(txt)
                text_content = "\n\n".join(valid_paras[:15])  # limit to first 15 paragraphs to keep it concise but rich
    except Exception as e:
        print(f"Error extracting from {url}: {e}")
        
    return text_content.strip(), image_url


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

            # 4. Article extractor: Fetch page for full-text and fallback/updated image
            full_text = ""
            if entry.link:
                extracted_text, page_image = extract_article_content_and_image(session, entry.link)
                if extracted_text:
                    full_text = extracted_text
                if page_image and not image_url:
                    image_url = page_image

            summary_cleaned = clean_html(
                entry.get("summary", entry.get("description", ""))
            )
            
            # Fallback if full_text extraction is empty
            if not full_text:
                full_text = summary_cleaned

            articles.append(
                {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": summary_cleaned,
                    "full_text": full_text,
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
