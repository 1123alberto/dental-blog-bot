import feedparser
from bs4 import BeautifulSoup

FEEDS = [
    "https://www.dentistrytoday.com/feed/",
    "https://bmcoralhealth.biomedcentral.com/articles/most-recent/rss.xml",
    "https://www.dentistryiq.com/rss",
]


def fetch_dental_news():
    articles = []
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
            if not image_url:
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

            articles.append(
                {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": clean_html(
                        entry.get("summary", entry.get("description", ""))
                    ),
                    "image": image_url,
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
