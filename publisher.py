import os
import re
from datetime import datetime

import markdown

OUTPUT_DIR = "/home/angelo/Gemini/dental-blog-bot/output"


def publish_blog_post(markdown_content):
    # Normalize headers to make parsing robust
    # 1. Remove optional numbering and bolding from main labels
    clean_md = re.sub(
        r"(?:\d\.\s+)?\*\*(Title|Teaser|SelectedImage|FullContent):\*\*",
        r"\1:",
        markdown_content,
    )
    # 2. Also handle non-bolded versions
    clean_md = re.sub(
        r"(?:\d\.\s+)?(Title|Teaser|SelectedImage|FullContent):\s*", r"\1: ", clean_md
    )

    title = "Weekly Dental Update"
    teaser = ""
    image_url = ""
    full_content_md = ""

    # Title
    title_match = re.search(r"Title:\s*(.*)", clean_md, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).split("\n")[0].strip().replace("**", "")

    # Teaser
    teaser_match = re.search(
        r"Teaser:\s*(.*?)(?=\n\s*(?:SelectedImage|FullContent|$))",
        clean_md,
        re.DOTALL | re.IGNORECASE,
    )
    if teaser_match:
        teaser = teaser_match.group(1).strip().replace("**", "")

    # SelectedImage
    image_match = re.search(r"SelectedImage:\s*(https?://\S+)", clean_md, re.IGNORECASE)
    if image_match:
        image_url = image_match.group(1).strip()

    # FullContent
    content_match = re.search(
        r"FullContent:\s*(.*)", clean_md, re.DOTALL | re.IGNORECASE
    )
    if content_match:
        full_content_md = content_match.group(1).strip()

    # Convert full content markdown to HTML
    full_content_html = markdown.markdown(full_content_md)

    # Use selected image or fallback gradient
    if image_url:
        image_html = (
            f'<img src="{image_url}" alt="{title}" class="w-full h-full object-cover">'
        )
    else:
        image_html = """
            <div class="h-full w-full bg-gradient-to-r from-cyan-500 to-blue-600 flex items-center justify-center relative overflow-hidden">
                <svg class="w-16 h-16 text-white opacity-20 absolute -right-4 -bottom-4 rotate-12" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                </svg>
                <div class="bg-white/20 p-4 rounded-2xl backdrop-blur-sm">
                    <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path>
                    </svg>
                </div>
            </div>"""

    # Create an expandable modern teaser card HTML
    html_card = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dental News</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #f3f4f6; display: flex; justify-content: center; align-items: start; min-height: 100vh; margin: 0; padding: 40px 20px; }}
        .content-transition {{ transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1); max-height: 0; opacity: 0; overflow: hidden; }}
        .expanded .content-transition {{ max-height: 2000px; opacity: 1; margin-top: 1.5rem; }}
        .prose h3 {{ font-weight: 700; color: #111827; margin-top: 1.5rem; margin-bottom: 0.5rem; font-size: 1.125rem; }}
        .prose p {{ margin-bottom: 1rem; color: #4b5563; }}
        .prose ul {{ list-style-type: disc; padding-left: 1.25rem; margin-bottom: 1rem; color: #4b5563; }}
        .prose li {{ margin-bottom: 0.25rem; }}
    </style>
</head>
<body>
    <div id="card" class="max-w-md w-full bg-white rounded-3xl shadow-2xl overflow-hidden border border-gray-100 transition-all duration-500 ease-in-out">
        <!-- Image Header -->
        <div class="h-48 overflow-hidden">
            {image_html}
        </div>

        <div class="p-8">
            <span class="inline-block px-3 py-1 bg-blue-50 text-blue-600 text-xs font-bold uppercase tracking-wider rounded-full mb-4">Latest News</span>
            <h2 class="text-2xl font-bold text-gray-900 mb-4 leading-tight">
                {title}
            </h2>
            <p id="teaser" class="text-gray-600 leading-relaxed">
                {teaser}
            </p>

            <!-- Expandable Content -->
            <div id="full-content" class="content-transition prose">
                {full_content_html}
            </div>

            <button onclick="toggleExpand()" id="btn" class="mt-8 w-full py-4 px-6 bg-gray-900 hover:bg-black text-white font-bold rounded-2xl transition-all duration-300 flex items-center justify-center gap-3 group">
                <span id="btn-text">Read More</span>
                <svg id="btn-icon" class="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path>
                </svg>
            </button>
        </div>
    </div>

    <script>
        function toggleExpand() {{
            const card = document.getElementById('card');
            const btnText = document.getElementById('btn-text');
            const btnIcon = document.getElementById('btn-icon');
            const isExpanded = card.classList.toggle('expanded');

            btnText.innerText = isExpanded ? 'Show Less' : 'Read More';
            btnIcon.style.transform = isExpanded ? 'rotate(90deg)' : 'rotate(0deg)';

            if (isExpanded) {{
                card.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        }}
    </script>
</body>
</html>"""

    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        date_str = datetime.now().strftime("%Y-%m-%d")
        file_name = f"news-{date_str}.html"
        file_path = os.path.join(OUTPUT_DIR, file_name)

        with open(file_path, "w") as f:
            f.write(html_card)

        return file_path
    except Exception as e:
        print(f"Error generating teaser card: {e}")
        return None
