import os
import json
import sys

# Reconfigure stdout and stderr to support UTF-8 and handle encoding errors gracefully
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

from generator import generate_blog_post
from publisher import publish_blog_post, WEBSITE_DATA_PATH, load_merged_posts
from scraper import fetch_dental_news
from agents import log_group_start, log_group_end


def main():
    log_group_start("[1] Fetching latest dental journal news & extracting article text")
    news_items = fetch_dental_news()
    log_group_end()

    if not news_items:
        print("No news found. Exiting.")
        return

    print(f"Fetched {len(news_items)} total entries from dental feeds.")

    # Load publication history to prevent duplicate topics
    recent_titles = []
    try:
        posts = load_merged_posts()
        # Extract titles of the last 10 published posts
        for post in posts[:10]:
            title = post.get("en", {}).get("title")
            if title:
                recent_titles.append(title)
        print(f"Loaded {len(recent_titles)} recently published article titles for topic avoidance:")
        for title in recent_titles:
            print(f"  - {title}")
    except Exception as e:
        print(f"Warning: Could not load publication history: {e}")

    print("[2] Running the 10-stage article generation pipeline...")
    blog_markdown = generate_blog_post(news_items, practice_name="Dentplant", recent_posts=recent_titles)

    if blog_markdown.startswith("Error"):
        print(f"CRITICAL ERROR: {blog_markdown}")
        sys.exit(1)

    log_group_start("[5] Publishing to output folder")
    file_path = publish_blog_post(blog_markdown)
    log_group_end()

    if file_path:
        filename = os.path.basename(file_path)
        print(f"\n" + "="*50)
        print(f"SUCCESS!")
        print(f"Post: {filename}")
        print(f"Path: {file_path}")
        print("="*50 + "\n")
    else:
        print("Failed to publish blog post.")
        sys.exit(1)


if __name__ == "__main__":
    main()

