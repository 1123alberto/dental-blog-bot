import os
import re
import json
from datetime import datetime
import markdown

OUTPUT_DIR = "/home/angelo/Gemini/dentplant/article"
WEBSITE_DATA_PATH = "/home/angelo/Gemini/dentplant/data/posts.json"

def clean_field(text):
    if not text: return ""
    text = text.replace("**", "").strip()
    return text

def parse_bilingual_content(markdown_content):
    data = {
        "source": "Dental News",
        "date": datetime.now().strftime("%B %d, %Y"),
        "image_url": "",
        "en": {"title": "", "teaser": "", "content": ""},
        "el": {"title": "", "teaser": "", "content": ""}
    }

    # Extract Common Fields
    source_match = re.search(r"\[SOURCE\]:\s*(.*)", markdown_content, re.IGNORECASE)
    if source_match: data["source"] = clean_field(source_match.group(1))

    date_match = re.search(r"\[DATE\]:\s*(.*)", markdown_content, re.IGNORECASE)
    if date_match: data["date"] = clean_field(date_match.group(1))

    image_match = re.search(r"\[IMAGE_URL\]:\s*(https?://\S+)", markdown_content, re.IGNORECASE)
    if image_match: data["image_url"] = image_match.group(1).strip()

    # Extract English Fields
    en_title = re.search(r"\[EN_TITLE\]:\s*(.*?)(?=\n\[|$)", markdown_content, re.DOTALL | re.IGNORECASE)
    if en_title: data["en"]["title"] = clean_field(en_title.group(1))

    en_teaser = re.search(r"\[EN_TEASER\]:\s*(.*?)(?=\n\[|$)", markdown_content, re.DOTALL | re.IGNORECASE)
    if en_teaser: data["en"]["teaser"] = clean_field(en_teaser.group(1))

    en_content = re.search(r"\[EN_CONTENT\]:\s*(.*?)(?=\n\[|---|$)", markdown_content, re.DOTALL | re.IGNORECASE)
    if en_content: data["en"]["content"] = markdown.markdown(en_content.group(1).strip())

    # Extract Greek Fields
    el_title = re.search(r"\[EL_TITLE\]:\s*(.*?)(?=\n\[|$)", markdown_content, re.DOTALL | re.IGNORECASE)
    if el_title: data["el"]["title"] = clean_field(el_title.group(1))

    el_teaser = re.search(r"\[EL_TEASER\]:\s*(.*?)(?=\n\[|$)", markdown_content, re.DOTALL | re.IGNORECASE)
    if el_teaser: data["el"]["teaser"] = clean_field(el_teaser.group(1))

    el_content = re.search(r"\[EL_CONTENT\]:\s*(.*?)(?=\n\[|---|$)", markdown_content, re.DOTALL | re.IGNORECASE)
    if el_content: data["el"]["content"] = markdown.markdown(el_content.group(1).strip())

    return data

def publish_blog_post(markdown_content):
    data = parse_bilingual_content(markdown_content)
    
    # Generate Standalone Filename
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_name = f"news-{date_str}"
    file_name = f"{base_name}.html"
    file_path = os.path.join(OUTPUT_DIR, file_name)
    
    counter = 0
    while os.path.exists(file_path):
        counter += 1
        file_name = f"{base_name}-{counter}.html"
        file_path = os.path.join(OUTPUT_DIR, file_name)

    # Use selected image or fallback
    image_html = f'<img src="{data["image_url"]}" alt="Dental News" class="w-full h-full object-cover">' if data["image_url"] else \
                 '<div class="h-full w-full bg-gradient-to-r from-cyan-500 to-blue-600"></div>'

    # Create Bilingual Standalone Page
    html_card = f"""<!DOCTYPE html>
<html lang="el">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data['el']['title']} | {data['en']['title']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #f3f4f6; }}
        [lang="en"] .lang-el, [lang="el"] .lang-en {{ display: none; }}
        .prose h3 {{ font-weight: 700; color: #111827; margin-top: 1.5rem; font-size: 1.25rem; }}
        .prose p {{ margin-bottom: 1rem; color: #4b5563; }}
        .prose ul {{ list-style-type: disc; padding-left: 1.25rem; margin-bottom: 1rem; color: #4b5563; }}
        .prose li {{ margin-bottom: 0.25rem; }}
    </style>
</head>
<body class="p-4 md:p-10 flex justify-center relative">
    <!-- Discreet Back Arrow -->
    <a href="../blog.html" class="fixed top-6 left-6 text-gray-400 hover:text-blue-600 transition-colors z-50 group" title="Back to Blog">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
    </a>

    <div class="max-w-3xl w-full bg-white rounded-3xl shadow-2xl overflow-hidden">
        <div class="h-[400px] w-full">{image_html}</div>
        <div class="p-8 md:p-12">
            <div class="flex justify-between items-center mb-6">
                <span class="px-3 py-1 bg-blue-50 text-blue-600 text-xs font-bold uppercase rounded-full">Breakthrough News</span>
                <button onclick="toggleLang()" class="text-xs font-bold text-gray-400 hover:text-blue-600">EN / ΕΛ</button>
            </div>
            
            <div class="lang-en">
                <h1 class="text-3xl font-bold text-gray-900 mb-4">{data['en']['title']}</h1>
                <p class="text-sm text-gray-400 mb-8">{data['source']} • {data['date']}</p>
                <div class="prose">{data['en']['content']}</div>
            </div>

            <div class="lang-el">
                <h1 class="text-3xl font-bold text-gray-900 mb-4">{data['el']['title']}</h1>
                <p class="text-sm text-gray-400 mb-8">{data['source']} • {data['date']}</p>
                <div class="prose">{data['el']['content']}</div>
            </div>
        </div>
    </div>
    <script>
        function toggleLang() {{
            const html = document.documentElement;
            html.lang = html.lang === 'el' ? 'en' : 'el';
            localStorage.setItem('lang', html.lang);
        }}
        // Apply saved language
        const savedLang = localStorage.getItem('lang') || 'el';
        document.documentElement.lang = savedLang;
    </script>
</body>
</html>"""

    try:
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        with open(file_path, "w") as f: f.write(html_card)

        # Update Website posts.json
        if os.path.exists(WEBSITE_DATA_PATH):
            with open(WEBSITE_DATA_PATH, "r") as f:
                posts = json.load(f)
            
            new_post = {
                "id": datetime.now().timestamp(),
                "date": data["date"],
                "source": data["source"],
                "image": data["image_url"],
                "url": f"article/{file_name}", # Path relative to blog.html
                "en": data["en"],
                "el": data["el"]
            }
            posts.insert(0, new_post) # Newest first
            with open(WEBSITE_DATA_PATH, "w") as f:
                json.dump(posts, f, indent=2, ensure_ascii=False)

        print(f"Bilingual post published to: {file_path}")
        return file_path
    except Exception as e:
        print(f"Error publishing: {e}")
        return None
