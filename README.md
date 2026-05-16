# 🦷 Dental Blog Bot

An automated tool that scrapes dental journals and uses AI to generate patient-friendly blog posts for your website.

## 📂 Project Structure
- main.py: The entry point. Run this to start the weekly process.
- scraper.py: Fetches latest articles from dental feeds.
- generator.py: Uses Gemini AI to draft the blog post.
- publisher.py: Wraps the AI content in your website's HTML template.
- output/: Folder where your new blog posts are saved for review.
- venv/: The virtual environment containing all required libraries.

## 🚀 How to Run Manually
To generate a new post anytime, run:
/home/angelo/Gemini/dental-blog-bot/venv/bin/python /home/angelo/Gemini/dental-blog-bot/main.py

## 📅 Automatic Scheduling (GitHub Actions)
The bot is configured to run automatically every Monday at 9:00 AM (Greece time) via GitHub Actions.

### Setup Instructions:
1.  **Push to GitHub**: 
    *   **Recommendation**: Push these bot files directly into your existing **dentplant** website repository. This makes it easy for the bot to find and update your files.
    *   If you keep them in a separate repository, you will need to adjust the `WEBSITE_PATH` in the workflow file.
2.  **Add API Key**:
    *   Go to your repository on GitHub.
    *   Navigate to **Settings > Secrets and variables > Actions**.
    *   Click **New repository secret**.
    *   Name: `GOOGLE_API_KEY`
    *   Value: Your Gemini API Key.
3.  **Permissions**:
    *   Go to **Settings > Actions > General**.
    *   Scroll to **Workflow permissions**.
    *   Select **Read and write permissions** (required for the bot to save posts back to the repo).

### Manual Trigger
You can also run the bot manually from GitHub:
-   Go to the **Actions** tab.
-   Select **Weekly Dental Blog Bot**.
-   Click **Run workflow**.

## ⚠️ Troubleshooting
- **Permission Denied**: Ensure "Workflow permissions" are set to "Read and write".
- **API Errors**: Check the Actions run logs for detailed error messages.
