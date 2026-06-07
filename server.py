import os
import sys
import json
import queue
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from scraper import fetch_dental_news
from publisher import load_merged_posts, publish_bilingual_data, parse_bilingual_content, unpublish_bilingual_data, render_preview_html_string
from agents import log_group_start, log_group_end
from agents.editorial_agent import deduplicate_articles, EditorialAgent, apply_history_filter
from agents.copywriter_agent import CopywriterAgent
from agents.qa_agent import QAAgent
from agents.memory import AgentMemory
from fastapi.staticfiles import StaticFiles
from google import genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/preview/article/draft.html")
async def get_draft_preview():
    if not state["temp_preview_html"]:
        raise HTTPException(status_code=404, detail="No preview active. Please generate or edit a draft first.")
    return HTMLResponse(content=state["temp_preview_html"])

app.mount("/preview", StaticFiles(directory="/home/angelo/Gemini/dentpant-new"), name="preview")

# Global logging redirector
log_queue = queue.Queue()

class QueueStream:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, data):
        self.original_stream.write(data)
        if data.strip():
            log_queue.put(data)

    def flush(self):
        self.original_stream.flush()

sys.stdout = QueueStream(sys.stdout)
sys.stderr = QueueStream(sys.stderr)

# Global state
state = {
    "is_running": False,
    "candidates": [],
    "recent_titles": [],
    "temp_preview_html": ""
}

class DraftRequest(BaseModel):
    index: int

class PublishRequest(BaseModel):
    source: str
    date: str
    image_url: str
    en: dict  # {"title": ..., "teaser": ..., "content": ...}
    el: dict  # {"title": ..., "teaser": ..., "content": ...}

class RejectRequest(BaseModel):
    file_name: str = None

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/events")
async def get_events():
    async def event_generator():
        while True:
            try:
                while not log_queue.empty():
                    line = log_queue.get_nowait()
                    yield f"data: {json.dumps({'log': line})}\n\n"
            except Exception:
                pass
            await asyncio.sleep(0.05)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/scrape")
async def scrape_candidates():
    if state["is_running"]:
        raise HTTPException(status_code=400, detail="Pipeline is currently active.")
    state["is_running"] = True
    
    # Clear log queue
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except queue.Empty:
            break
            
    print("[Server] Starting Scraper and Editorial Agent...")
    try:
        log_group_start("[1] Fetching latest dental journal news & extracting article text")
        news_items = fetch_dental_news()
        log_group_end()
        
        if not news_items:
            print("[Server] No news items found.")
            state["is_running"] = False
            return {"candidates": []}
            
        print(f"[Server] Fetched {len(news_items)} news items.")
        
        # Load history
        recent_titles = []
        try:
            posts = load_merged_posts()
            for post in posts[:10]:
                title = post.get("en", {}).get("title")
                if title:
                    recent_titles.append(title)
            state["recent_titles"] = recent_titles
        except Exception as e:
            print(f"[Server] Warning loading publication history: {e}")
            
        log_group_start("[2] Editorial Evaluation & Article Selection")
        # Deduplicate
        unique_articles = deduplicate_articles(news_items)
        
        # Initialize Gemini Client
        api_key = os.getenv("GOOGLE_API_KEY")
        client = None
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"[Server] Warning initializing Gemini client: {e}")
                
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        editorial_agent = EditorialAgent(client=client, model_name=model_name)
        
        # Score & classify
        editorial_agent.score_and_classify(unique_articles)
        
        # Apply history filter
        apply_history_filter(unique_articles, recent_titles)
        log_group_end()
        
        # Sort by final_score descending
        unique_articles.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        state["candidates"] = unique_articles
        
        # Print list for console logs
        print(f"\n[Server] Scored {len(unique_articles)} candidates successfully.")
        for idx, art in enumerate(unique_articles):
            print(f"  [{idx}] Score: {art.get('final_score')} - {art.get('title')} (Inappropriate: {art.get('is_inappropriate')})")
            
        state["is_running"] = False
        return {"candidates": unique_articles}
    except Exception as e:
        state["is_running"] = False
        print(f"[Server] Scraper/Editorial error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/draft")
async def generate_draft(req: DraftRequest):
    if state["is_running"]:
        raise HTTPException(status_code=400, detail="Pipeline is currently active.")
    if req.index < 0 or req.index >= len(state["candidates"]):
        raise HTTPException(status_code=400, detail="Invalid candidate index.")
        
    state["is_running"] = True
    print(f"[Server] Starting copywriting draft for candidate index {req.index}...")
    try:
        candidate = state["candidates"][req.index]
        
        # Initialize Gemini Client
        api_key = os.getenv("GOOGLE_API_KEY")
        client = None
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"[Server] Warning: Could not initialize Gemini client: {e}")
                
        if not client:
            state["is_running"] = False
            raise HTTPException(status_code=400, detail="Gemini client could not be initialized (missing/invalid GOOGLE_API_KEY).")
            
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        
        memory = AgentMemory()
        copywriter_agent = CopywriterAgent(client=client, model_name=model_name)
        qa_agent = QAAgent(client=client, model_name=model_name)
        
        log_group_start("[3] Copywriter Drafting (Bilingual)")
        blog_markdown = copywriter_agent.write_post(candidate, "Dentplant", memory)
        log_group_end()
        
        log_group_start("[4] QA Validation Feedback Loop")
        max_qa_attempts = 3
        for attempt in range(max_qa_attempts):
            print(f"[Pipeline] Running QA Agent validation (Attempt {attempt+1}/{max_qa_attempts})...")
            is_valid, errors = qa_agent.validate_post(blog_markdown, "Dentplant")
            if is_valid:
                print("[Pipeline] QA Validation SUCCESS!")
                break
            else:
                print(f"[Pipeline] QA Validation FAILED with errors:")
                for err in errors:
                    print(f"  - {err}")
                    memory.add_lesson(
                        category="copywriting",
                        error_description=err,
                        correction_rule=f"Do not repeat error: {err}. Adhere strictly to the guidelines."
                    )
                if attempt < max_qa_attempts - 1:
                    blog_markdown = copywriter_agent.refine_post(blog_markdown, errors, candidate, "Dentplant")
                else:
                    print("[Pipeline] Max QA attempts reached. Proceeding with best available draft.")
        log_group_end()
        
        # Parse the generated markdown
        parsed_data = parse_bilingual_content(blog_markdown)
        state["is_running"] = False
        return parsed_data
    except Exception as e:
        state["is_running"] = False
        print(f"[Server] Copywriting draft error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/publish")
async def publish_locally(req: PublishRequest):
    print("[Server] Saving and publishing locally...")
    try:
        data = req.dict()
        file_path = publish_bilingual_data(data)
        if file_path:
            return {"status": "success", "file_name": os.path.basename(file_path)}
        else:
            raise HTTPException(status_code=500, detail="Failed to publish article locally.")
    except Exception as e:
        print(f"[Server] Local publication error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reject")
async def reject_draft(req: RejectRequest):
    print("[Server] Rejecting draft...")
    try:
        if req.file_name:
            print(f"[Server] Discarding and deleting published files for: {req.file_name}")
            success = unpublish_bilingual_data(req.file_name)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to delete local published files during rejection.")
        print("[Server] Draft discarded successfully.")
        return {"status": "success"}
    except Exception as e:
        print(f"[Server] Error during draft rejection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/preview_draft")
async def preview_draft(req: PublishRequest):
    print("[Server] Compiling temporary draft preview...")
    try:
        data = req.dict()
        state["temp_preview_html"] = render_preview_html_string(data)
        return {"status": "success"}
    except Exception as e:
        print(f"[Server] Error rendering preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))
