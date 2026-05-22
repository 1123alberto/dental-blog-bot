from scraper import fetch_dental_news
from agents.base import BaseAgent

class ScraperAgent(BaseAgent):
    """
    ScraperAgent manages feed discovery, content downloading, image scraping,
    and initial sanitization of the raw articles.
    """
    def __init__(self, client=None, model_name="gemini-3.5-flash"):
        super().__init__(client, model_name)

    def scrape_and_curate(self):
        """
        Triggers feed parsing, text crawling, and formats the output list of raw articles.
        """
        print("[ScraperAgent] Triggering scraping pipeline from RSS feeds...")
        try:
            articles = fetch_dental_news()
            print(f"[ScraperAgent] Successfully scraped {len(articles)} articles.")
            
            # Perform basic sanitization
            curated_articles = []
            for art in articles:
                title = art.get("title", "").strip()
                source = art.get("source", "Dental Journal").strip()
                link = art.get("link", "").strip()
                summary = art.get("summary", "").strip()
                full_text = art.get("full_text", "").strip()
                image = art.get("image")
                date = art.get("date", "Recently").strip()

                if not title:
                    continue

                # Ensure image URL is cleaned up
                if image:
                    image = image.strip()

                curated_articles.append({
                    "title": title,
                    "source": source,
                    "link": link,
                    "summary": summary,
                    "full_text": full_text if full_text else summary,
                    "image": image,
                    "date": date
                })

            return curated_articles
        except Exception as e:
            print(f"[ScraperAgent] Critical error during scraping: {e}")
            return []
