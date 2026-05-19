# 🦷 Dental Blog Bot

An automated tool that scrapes dental journals and uses AI to generate patient-friendly, bilingual blog posts for your website.

## 📂 Project Structure

- `main.py`: The entry point. Run this to start the scraping and generation process.
- `scraper.py`: Fetches the latest articles from dental feeds.
- `generator.py`: Uses Gemini AI (`gemini-flash-latest`) to draft the blog post.
- `publisher.py`: Formats the content into a bilingual HTML template and updates the posts index.
- `.github/workflows/weekly_blog.yml`: GitHub Actions workflow for automated weekly execution.
- `output/`: Folder where a backup copy of new blog posts is saved locally.

---

## ⚙️ Configuration & Environment Variables

The bot uses the following environment variables (which can be defined in a local `.env` file):

| Environment Variable | Description | Default Value |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | **[Required]** Your Google Gemini API key. | None |
| `WEBSITE_PATH` | Path to the website repository root. | `~/Gemini/dentpant-new` |
| `OUTPUT_DIR` | Directory where individual HTML blog posts will be saved. | `WEBSITE_PATH/article` |
| `WEBSITE_DATA_PATH` | Path to the website's posts database JSON file. | `WEBSITE_PATH/data/posts.json` |

---

## 🚀 Local Setup & Run

1. **Install Dependencies**:
   Ensure you have Python 3.10+ installed. In your virtual environment, run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and fill in your Gemini API key:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

3. **Run the Bot**:
   ```bash
   python main.py
   ```
   *Note: If `WEBSITE_PATH` is configured and points to your local website repository, the post will be directly generated in your website's folder, and its database JSON will be updated.*

---

## 📅 Automatic Scheduling (GitHub Actions)

The bot runs automatically every Monday at 9:00 AM (Greece time) via GitHub Actions. It is configured to run from this repository, pull the website repository (`1123alberto/dentplant-new`), write the newly generated post, and push the updates back.

### Setup Instructions on GitHub:

1. **Add Secrets**:
   Go to your bot repository on GitHub, navigate to **Settings > Secrets and variables > Actions**, and click **New repository secret** to add:
   * **`GOOGLE_API_KEY`**: Your Gemini API Key.
   * **`WEBSITE_PUSH_PAT`**: A Personal Access Token (PAT) with `repo` scope permissions. This is required for the action to pull and push changes to the separate website repository (`1123alberto/dentplant-new`).

2. **Manual Trigger**:
   You can also run the bot manually from GitHub:
   * Go to the **Actions** tab of this repository.
   * Select **Weekly Dental Blog Bot** from the sidebar.
   * Click **Run workflow** -> **Run workflow**.

---

## ⚠️ Troubleshooting

- **API Errors**: Verify that your `GOOGLE_API_KEY` is correct and has not expired.
- **Git Push/Authentication Errors**: Ensure the `WEBSITE_PUSH_PAT` secret is configured correctly with write access to `1123alberto/dentplant-new`.
