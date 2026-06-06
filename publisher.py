import os
import re
import json
from datetime import datetime
import markdown

# Environment-aware paths
# Defaults to local structure, but can be overridden in GitHub Actions
BASE_DIR = os.getenv("WEBSITE_PATH", os.path.expanduser("~/Gemini/dentpant-new"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(BASE_DIR, "article"))
WEBSITE_DATA_PATH = os.environ.get("WEBSITE_DATA_PATH", os.path.join(BASE_DIR, "data", "posts.json"))

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

def slugify(text):
    if not text: return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

def escape_js_quotes(text):
    if not text: return ""
    return text.replace('"', '\\"').replace("'", "\\'")

def escape_html_attr(text):
    if not text: return ""
    return text.replace('"', '&quot;')

def get_iso_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")

def update_static_blog_html(posts):
    blog_html_path = os.path.join(BASE_DIR, "blog.html")
    if not os.path.exists(blog_html_path):
        print(f"Warning: blog.html not found at {blog_html_path}. Cannot update static cards.")
        return False

    recent_posts = posts[:12]
    cards_html = ["\n      <!-- STATIC_BLOG_POSTS_START -->"]
    for i, post in enumerate(recent_posts, 1):
        date_str = post.get("date", "")
        img_src = post.get("image", "")
        url_path = post.get("url", "")
        
        el_title = post.get("el", {}).get("title", "")
        el_teaser = post.get("el", {}).get("teaser", "")
        en_title = post.get("en", {}).get("title", "")
        en_teaser = post.get("en", {}).get("teaser", "")
        
        card = f"""
      <!-- Article {i} -->
      <article class="blog-card tactile-card bg-white overflow-hidden flex flex-col transition-all duration-300">
        <div class="relative h-56 overflow-hidden bg-white/20 p-2">
          <img src="{img_src}" alt="{en_title or 'Blog Image'}" class="w-full h-full object-cover rounded-md shadow-inner transition-transform duration-500 hover:scale-105" loading="lazy">
        </div>
        <div class="p-6 flex flex-col flex-grow">
          <div class="text-[10px] text-teal-800/60 font-semibold mb-2 uppercase tracking-widest">{date_str}</div>
          <h2 class="text-lg font-serif font-bold text-teal-950 mb-3 line-clamp-2 leading-tight hover:text-teal-600 transition-colors">
            <a href="{url_path}" class="lang-el">{el_title}</a>
            <a href="{url_path}" class="lang-en">{en_title}</a>
          </h2>
          <p class="text-xs text-soft-text leading-relaxed line-clamp-3 flex-grow lang-el">{el_teaser}</p>
          <p class="text-xs text-soft-text leading-relaxed line-clamp-3 flex-grow lang-en">{en_teaser}</p>
          <a href="{url_path}" class="mt-4 inline-flex items-center text-[10px] font-bold text-teal-600 uppercase tracking-widest group hover:text-teal-500 transition-colors lang-el">
            ΔΙΑΒΑΣΤΕ ΠΕΡΙΣΣΟΤΕΡΑ
            <svg class="ml-1 w-3 h-3 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
            </svg>
          </a>
          <a href="{url_path}" class="mt-4 inline-flex items-center text-[10px] font-bold text-teal-600 uppercase tracking-widest group hover:text-teal-500 transition-colors lang-en">
            READ MORE
            <svg class="ml-1 w-3 h-3 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
            </svg>
          </a>
        </div>
      </article>"""
        cards_html.append(card)
        
    cards_html.append("      <!-- STATIC_BLOG_POSTS_END -->\n    ")
    generated_block = "\n".join(cards_html)

    try:
        with open(blog_html_path, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = r"<!-- STATIC_BLOG_POSTS_START -->.*?<!-- STATIC_BLOG_POSTS_END -->"
        if not re.search(pattern, content, re.DOTALL):
            print("Warning: Could not find STATIC_BLOG_POSTS comments in blog.html. Skipping static updates.")
            return False

        updated_content = re.sub(pattern, generated_block, content, flags=re.DOTALL)
        with open(blog_html_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        print(f"Successfully updated static cards in {blog_html_path}")
        return True
    except Exception as e:
        print(f"Error updating static blog cards in blog.html: {e}")
        return False

def create_google_post_assets(data, file_name, json_image_path):
    try:
        import shutil
        
        # 1. Determine paths
        slug = os.path.splitext(file_name)[0]
        local_output = os.path.join(os.path.dirname(__file__), "output")
        google_post_dir = os.path.join(local_output, "google_posts", slug)
        os.makedirs(google_post_dir, exist_ok=True)

        # 2. Save CTA URL
        cta_url = f"https://www.dentplant.gr/article/{file_name}"
        with open(os.path.join(google_post_dir, "cta_url.txt"), "w", encoding="utf-8") as f:
            f.write(cta_url)

        # 3. Save photo link and copy the image
        img_url = data.get("image_url", "")
        with open(os.path.join(google_post_dir, "photo_link.txt"), "w", encoding="utf-8") as f:
            f.write(f"Original: {img_url}\n")
            if json_image_path:
                f.write(f"Localized: {json_image_path}\n")

        # Copy and convert localized image to JPG if available
        if json_image_path and not json_image_path.startswith(("http://", "https://")):
            cleaned_img_path = json_image_path
            if cleaned_img_path.startswith("../"):
                cleaned_img_path = cleaned_img_path[3:]
            absolute_img_path = os.path.join(BASE_DIR, cleaned_img_path)
            if os.path.exists(absolute_img_path):
                try:
                    from PIL import Image
                    dest_path = os.path.join(google_post_dir, "photo.jpg")
                    with Image.open(absolute_img_path) as img:
                        if img.mode in ("RGBA", "LA", "P"):
                            img = img.convert("RGB")
                        img.save(dest_path, "JPEG", quality=90)
                    print(f"Converted and saved Google Post photo asset: {absolute_img_path} -> photo.jpg")
                except Exception as e:
                    print(f"Error converting image to JPG: {e}. Falling back to copying original.")
                    shutil.copy2(absolute_img_path, os.path.join(google_post_dir, "photo.jpg"))

        # 4. Generate teasers & hooks
        el_title = data.get("el", {}).get("title", "")
        el_teaser = data.get("el", {}).get("teaser", "")
        en_title = data.get("en", {}).get("title", "")
        en_teaser = data.get("en", {}).get("teaser", "")

        # EL Post
        el_post = f"📢 {el_title}\n\n{el_teaser}\n\n🔍 Διαβάστε ολόκληρο το άρθρο στην ιστοσελίδα μας για να μάθετε περισσότερα σχετικά με τις τελευταίες επιστημονικές εξελίξεις στην οδοντιατρική φροντίδα!"
        with open(os.path.join(google_post_dir, "post_content_el.txt"), "w", encoding="utf-8") as f:
            f.write(el_post)

        # EN Post
        en_post = f"📢 {en_title}\n\n{en_teaser}\n\n🔍 Read the full article on our website to learn more about the latest scientific developments in dental care!"
        with open(os.path.join(google_post_dir, "post_content_en.txt"), "w", encoding="utf-8") as f:
            f.write(en_post)

        # Combined Post
        combined_post = f"{el_post}\n\n=====================\n\n{en_post}"
        with open(os.path.join(google_post_dir, "post_content_combined.txt"), "w", encoding="utf-8") as f:
            f.write(combined_post)

        print(f"Google Business Profile post assets generated at: {google_post_dir}")
        return google_post_dir
    except Exception as e:
        print(f"Error generating Google Business Profile post assets: {e}")
        return None

def load_merged_posts():
    """
    Loads posts from both WEBSITE_DATA_PATH and local posts_backup.json,
    merges them uniquely by 'url', and sorts them descending by 'id' (newest first).
    """
    posts_dict = {}
    
    # Try loading from WEBSITE_DATA_PATH
    if os.path.exists(WEBSITE_DATA_PATH):
        try:
            with open(WEBSITE_DATA_PATH, "r", encoding="utf-8") as f:
                website_posts = json.load(f)
                if isinstance(website_posts, list):
                    for post in website_posts:
                        url = post.get("url")
                        if url:
                            posts_dict[url] = post
        except Exception as e:
            print(f"Warning: Could not read website posts.json: {e}")

    # Try loading from local posts_backup.json
    local_output = os.path.join(os.path.dirname(__file__), "output")
    local_posts_backup = os.path.join(local_output, "posts_backup.json")
    if os.path.exists(local_posts_backup):
        try:
            with open(local_posts_backup, "r", encoding="utf-8") as f:
                backup_posts = json.load(f)
                if isinstance(backup_posts, list):
                    for post in backup_posts:
                        url = post.get("url")
                        if url:
                            if url not in posts_dict:
                                posts_dict[url] = post
        except Exception as e:
            print(f"Warning: Could not read local posts_backup.json: {e}")

    merged_posts = list(posts_dict.values())
    
    # Sort descending by ID. If ID is missing or invalid, fall back to 0.0
    def get_sort_key(post):
        post_id = post.get("id")
        try:
            return float(post_id)
        except (TypeError, ValueError):
            return 0.0
            
    merged_posts.sort(key=get_sort_key, reverse=True)
    return merged_posts


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

    # Localize and optimize external images
    json_image_path = ""
    html_image_path = ""
    if data["image_url"]:
        if data["image_url"].startswith(("http://", "https://")):
            try:
                import urllib.request
                from PIL import Image
                import io
                
                title_slug = slugify(data["en"]["title"]) if data["en"]["title"] else "blog_image"
                if not title_slug:
                    title_slug = "blog_image"
                    
                img_filename = f"{title_slug}.webp"
                target_img_dir = os.path.join(BASE_DIR, "images", "blog")
                os.makedirs(target_img_dir, exist_ok=True)
                
                target_img_path = os.path.join(target_img_dir, img_filename)
                img_counter = 0
                base_img_name = title_slug
                while os.path.exists(target_img_path):
                    img_counter += 1
                    img_filename = f"{base_img_name}_{img_counter}.webp"
                    target_img_path = os.path.join(target_img_dir, img_filename)
                    
                print(f"Downloading external image: {data['image_url']}")
                req = urllib.request.Request(data["image_url"], headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=15) as response:
                    img_data = response.read()
                    
                img = Image.open(io.BytesIO(img_data))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(target_img_path, "WEBP", quality=85)
                print(f"Successfully localized image: {target_img_path}")
                
                json_image_path = f"images/blog/{img_filename}"
                html_image_path = f"../images/blog/{img_filename}"
            except Exception as e:
                print(f"Error localizing image: {e}")
                json_image_path = data["image_url"]
                html_image_path = data["image_url"]
        else:
            json_image_path = data["image_url"]
            if json_image_path.startswith("images/"):
                html_image_path = f"../{json_image_path}"
            else:
                html_image_path = json_image_path

    # Construct image html
    if html_image_path:
        image_html = f'<img src="{html_image_path}" alt="Dental News" class="w-full h-full object-cover">'
    else:
        image_html = '<div class="h-full w-full bg-gradient-to-r from-cyan-500 to-blue-600"></div>'

    # Get ISO date format for JSON-LD
    iso_date = get_iso_date(data["date"])

    # Prepare escaped fields for HTML and JS script attributes
    el_title_esc = escape_js_quotes(data['el']['title'])
    en_title_esc = escape_js_quotes(data['en']['title'])
    el_teaser_attr = escape_html_attr(data['el']['teaser'])
    en_teaser_attr = escape_html_attr(data['en']['teaser'])

    # Create Bilingual Standalone Page
    html_card = f"""<!DOCTYPE html>
<html lang="el">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data['el']['title']} | {data['en']['title']}</title>
    <meta name="description" content="{el_teaser_attr}">
    <link rel="canonical" href="https://www.dentplant.gr/article/{file_name}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://www.dentplant.gr/article/{file_name}">
    <meta property="og:title" content="{data['el']['title']} | {data['en']['title']}">
    <meta property="og:description" content="{el_teaser_attr}">
    {f'<meta property="og:image" content="https://www.dentplant.gr/{json_image_path}">' if json_image_path else ""}
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="https://www.dentplant.gr/article/{file_name}">
    <meta name="twitter:title" content="{data['el']['title']} | {data['en']['title']}">
    <meta name="twitter:description" content="{el_teaser_attr}">
    {f'<meta name="twitter:image" content="https://www.dentplant.gr/{json_image_path}">' if json_image_path else ""}

    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="../css/fonts.css">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #f3f4f6; }}
        [lang="en"] .lang-el, [lang="el"] .lang-en {{ display: none; }}
        .prose h3 {{ font-weight: 700; color: #111827; margin-top: 1.5rem; font-size: 1.25rem; }}
        .prose p {{ margin-bottom: 1rem; color: #4b5563; }}
        .prose ul {{ list-style-type: disc; padding-left: 1.25rem; margin-bottom: 1rem; color: #4b5563; }}
        .prose li {{ margin-bottom: 0.25rem; }}
    </style>

    <!-- JSON-LD Structured Data for Blog Article -->
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "headline": "{el_title_esc} | {en_title_esc}",
      "description": "{el_teaser_attr}",
      "image": "{f'https://www.dentplant.gr/{json_image_path}' if json_image_path else 'https://www.dentplant.gr/assets/images/logo.png'}",
      "datePublished": "{iso_date}",
      "author": {{
        "@type": "Organization",
        "name": "Dentplant"
      }},
      "publisher": {{
        "@type": "Organization",
        "name": "Dentplant",
        "logo": {{
          "@type": "ImageObject",
          "url": "https://www.dentplant.gr/assets/images/logo.png"
        }}
      }},
      "mainEntityOfPage": {{
        "@type": "WebPage",
        "@id": "https://www.dentplant.gr/article/{file_name}"
      }}
    }}
    </script>
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
        const titles = {{
            'el': "{el_title_esc} | Dentplant",
            'en': "{en_title_esc} | Dentplant"
        }};
        function toggleLang() {{
            const html = document.documentElement;
            html.lang = html.lang === 'el' ? 'en' : 'el';
            sessionStorage.setItem('lang', html.lang);
            document.title = titles[html.lang];
        }}
        // Apply saved language
        const savedLang = sessionStorage.getItem('lang') || 'el';
        document.documentElement.lang = savedLang;
        document.title = titles[savedLang];
    </script>
</body>
</html>"""

    try:
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        with open(file_path, "w", encoding="utf-8") as f: f.write(html_card)

        # REDUNDANCY: Also save a copy in the local bot folder
        local_output = os.path.join(os.path.dirname(__file__), "output")
        if not os.path.exists(local_output): os.makedirs(local_output)
        local_file_path = os.path.join(local_output, file_name)
        with open(local_file_path, "w", encoding="utf-8") as f: f.write(html_card)

        # Update Website posts.json and local posts_backup.json via merge logic
        posts = load_merged_posts()

        # Construct new post entry
        new_post = {
            "id": datetime.now().timestamp(),
            "date": data["date"],
            "source": data["source"],
            "image": json_image_path,
            "url": f"article/{file_name}", # Path relative to blog.html
            "en": data["en"],
            "el": data["el"]
        }
        
        # Prevent duplicates by filtering out any existing post with the same URL
        posts = [p for p in posts if p.get("url") != new_post["url"]]
        posts.insert(0, new_post)

        # Save back to WEBSITE_DATA_PATH if its directory exists
        if os.path.exists(os.path.dirname(WEBSITE_DATA_PATH)):
            try:
                with open(WEBSITE_DATA_PATH, "w", encoding="utf-8") as f:
                    json.dump(posts, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving website posts.json: {e}")

        # Always save a copy in the local output folder as posts_backup.json
        local_posts_backup = os.path.join(local_output, "posts_backup.json")
        try:
            with open(local_posts_backup, "w", encoding="utf-8") as f:
                json.dump(posts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving local posts_backup.json: {e}")

        # Update static blog cards in blog.html
        update_static_blog_html(posts)

        # Generate Google Business Profile post assets
        create_google_post_assets(data, file_name, json_image_path)

        print(f"Bilingual post published to: {file_path}")
        return file_path
    except Exception as e:
        print(f"Error publishing: {e}")
        return None
