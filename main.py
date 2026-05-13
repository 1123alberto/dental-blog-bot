from generator import generate_blog_post
from publisher import publish_blog_post
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
            f"Summary: {item['summary']}\n"
            f"ImageURL: {item['image']}\n\n"
        )

    print("[2] Generating blog post with AI...")
    blog_markdown = generate_blog_post(news_data, practice_name="Dentplant")

    if blog_markdown.startswith("Error:"):
        print(blog_markdown)
        return

    print("[3] Publishing to output folder...")
    file_path = publish_blog_post(blog_markdown)

    if file_path:
        msg = f"\nSuccess! Your new blog post is ready for review at: {file_path}"
        print(msg)
    else:
        print("Failed to publish blog post.")


if __name__ == "__main__":
    main()
