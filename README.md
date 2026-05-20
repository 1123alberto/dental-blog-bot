# 🦷 Dental Blog Bot

An automated tool that scrapes dental journals and uses AI to generate patient-friendly, bilingual blog posts for your website.

## 📂 Project Structure

- `main.py`: The entry point. Orchestrates the 10-stage pipeline.
- `scraper.py`: Fetches and extracts full text from the latest dental journals and RSS feeds.
- `generator.py`: The "brain" of the bot. Contains the deduplication, scoring, and writing logic using Gemini AI.
- `publisher.py`: Handles formatting, local backups, and updating the website's posts database.
- `.github/workflows/weekly_blog.yml`: GitHub Actions workflow for automated weekly execution.
- `output/`: Folder where a backup copy of every generated blog post is saved.

---

## 🧠 The 10-Stage Pipeline

The bot now follows a sophisticated editorial process to ensure high-quality content:

1.  **Fetching**: Aggregates news from multiple high-authority dental feeds.
2.  **Extraction**: Pulls full article text and identifies the best available images.
3.  **Deduplication**: Uses Jaccard similarity to group and filter out redundant stories.
4.  **Scoring**: AI evaluates articles on clinical relevance, credibility, and educational value.
5.  **Classification**: Automatically categorizes articles (e.g., Implantology, Periodontology, Digital Dentistry).
6.  **Image Validation**: Ranks images, prioritizing clinical/authentic visuals over stock/AI fallbacks.
7.  **History Filtering**: Checks against recently published articles to avoid repetitive topics.
8.  **Candidate Selection**: Filters down to the Top 3 highest-quality candidates.
9.  **Editorial Decision**: Gemini acts as "Editor-in-Chief" to select the single best story for the week.
10. **Bilingual Generation**: Drafts a professional, patient-friendly post in both **English and Greek**.

---

## ⚙️ Configuration & Environment Variables

The bot uses the following environment variables (defined in a `.env` file):

| Environment Variable | Description | Default Value |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | **[Required]** Your Google Gemini API key. | None |
| `WEBSITE_PATH` | Path to the website repository root. | `website` (in CI) |
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
   Copy `.env.example` to `.env` and fill in your Gemini API key.

3. **Run the Bot**:
   ```bash
   python main.py
   ```
   *Note: The bot will automatically check your local `posts.json` (if configured) to ensure it doesn't repeat recent topics.*

---

## 📅 Automatic Scheduling (GitHub Actions)

The bot runs automatically every **Monday at 9:00 AM (Greece time)**. 

### Automated Workflow:
1.  Checks out this repository.
2.  Clones the website repository (`1123alberto/dentplant-new`).
3.  Runs the 10-stage pipeline to generate a new post.
4.  Updates the website's database and saves the new article.
5.  Pushes the changes back to the website repository.

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

- **API Errors**: Verify that your `GOOGLE_API_KEY` is correct. The bot includes multi-model fallback to improve reliability.
- **Git Push/Authentication Errors**: Ensure the `WEBSITE_PUSH_PAT` secret is configured correctly with write access to `1123alberto/dentplant-new`.
- **Empty Publishes**: The pipeline includes error detection to prevent empty files from being pushed if the AI generation fails.
