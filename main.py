import os
import json
from generator import generate_blog_post
from publisher import publish_blog_post, WEBSITE_DATA_PATH
from scraper import fetch_dental_news


def main():
    print("[1] Fetching latest dental journal news...")
    news_items = fetch_dental_news()

    if not news_items:
        print("No news found. Exiting.")
        return

    # Combine news for the AI, including image URLs for selection
    news_data = ""
    for i, item in enumerate(news_items):
        news_data += (
            f"--- Article {i} ---\n"
            f"Title: {item['title']}\n"
            f"Source: {item['source']}\n"
            f"Date: {item['date']}\n"
            f"Summary: {item['summary']}\n"
            f"ImageURL: {item['image']}\n\n"
        )

    # Load publication history to prevent duplicate topics
    recent_titles = []
    if os.path.exists(WEBSITE_DATA_PATH):
        try:
            with open(WEBSITE_DATA_PATH, "r") as f:
                posts = json.load(f)
                # Extract titles of the last 10 published posts
                for post in posts[:10]:
                    title = post.get("en", {}).get("title")
                    if title:
                        recent_titles.append(title)
            print(f"Loaded {len(recent_titles)} recently published article titles for topic avoidance:")
            for title in recent_titles:
                print(f"  - {title}")
        except Exception as e:
            print(f"Warning: Could not load publication history from {WEBSITE_DATA_PATH}: {e}")
    else:
        print(f"No publication history found at {WEBSITE_DATA_PATH}. Topic avoidance is disabled.")

    print("[2] Generating blog post with AI...")
    blog_markdown = generate_blog_post(news_data, practice_name="Dentplant", recent_posts=recent_titles)

    if blog_markdown.startswith("Error"):
        print(blog_markdown)
        return

    print(f"[3] Publishing to output folder...")
    file_path = publish_blog_post(blog_markdown)

    if file_path:
        filename = os.path.basename(file_path)
        print(f"\n" + "="*50)
        print(f"🚀 SUCCESS!")
        print(f"📄 Post: {filename}")
        print(f"📍 Path: {file_path}")
        print("="*50 + "\n")
    else:
        print("❌ Failed to publish blog post.")


if __name__ == "__main__":
    main()
