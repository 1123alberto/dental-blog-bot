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

## 📅 Automatic Scheduling (Cron)
The bot is designed to run every Monday at 9:00 AM.
Current Schedule:
0 9 * * 1 cd /home/angelo/Gemini/dental-blog-bot && ./venv/bin/python main.py >> cron_log.txt 2>&1

## ⚠️ Troubleshooting
- Laptop is off: If the laptop is off at 9 AM Monday, the script will not run. Run it manually.
- API Errors: Check cron_log.txt for errors like Quota Exceeded.
