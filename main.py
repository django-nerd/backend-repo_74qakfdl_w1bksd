import os
import random
import math
from typing import List, Optional
from fastapi import FastAPI, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PromptRequest(BaseModel):
    prompt: str
    width: int = 800
    height: int = 500
    seed: Optional[int] = None
    theme: str = "slate"


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


# ---------------- Text-to-Sketch Logic ---------------- #

def rng(seed: Optional[int]):
    rnd = random.Random(seed)
    return rnd


def jitter(rnd: random.Random, val: float, scale: float = 1.0) -> float:
    return val + (rnd.random() - 0.5) * scale


def rough_line(rnd: random.Random, x1: float, y1: float, x2: float, y2: float, stroke: str) -> str:
    # draw two jittered lines to mimic hand-drawn
    dx = x2 - x1
    dy = y2 - y1
    segs = []
    for i in range(2):
        jx1 = jitter(rnd, x1, scale=2.2)
        jy1 = jitter(rnd, y1, scale=2.2)
        jx2 = jitter(rnd, x2, scale=2.2)
        jy2 = jitter(rnd, y2, scale=2.2)
        segs.append(f'<path d="M {jx1:.1f},{jy1:.1f} L {jx2:.1f},{jy2:.1f}" stroke="{stroke}" stroke-width="1.8" fill="none" stroke-linecap="round" opacity="0.9" />')
    return "\n".join(segs)


def rough_rect(rnd: random.Random, x: float, y: float, w: float, h: float, stroke: str, fill: Optional[str] = None) -> str:
    # fill with subtle hatch
    parts: List[str] = []
    if fill:
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" opacity="0.1" rx="8" />')
    parts.append(rough_line(rnd, x, y, x+w, y, stroke))
    parts.append(rough_line(rnd, x+w, y, x+w, y+h, stroke))
    parts.append(rough_line(rnd, x+w, y+h, x, y+h, stroke))
    parts.append(rough_line(rnd, x, y+h, x, y, stroke))
    return "\n".join(parts)


def rough_circle(rnd: random.Random, cx: float, cy: float, r: float, stroke: str, fill: Optional[str] = None) -> str:
    parts: List[str] = []
    if fill:
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" opacity="0.1" />')
    # approximate circle with polygons jittered
    for i in range(2):
        pts = []
        for a in range(0, 360, 20):
            ang = math.radians(a + jitter(rnd, 0, 2))
            rr = r + jitter(rnd, 0, 1.5)
            x = cx + rr * math.cos(ang)
            y = cy + rr * math.sin(ang)
            pts.append(f"{x:.1f},{y:.1f}")
        parts.append(f'<polyline points="{' '.join(pts)}" fill="none" stroke="{stroke}" stroke-width="1.6" opacity="0.9" />')
    return "\n".join(parts)


def text_el(x: float, y: float, content: str, color: str) -> str:
    safe = content.replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-family="Inter, system-ui, -apple-system, Segoe UI, Roboto" font-size="14" opacity="0.9">{safe}</text>'


THEMES = {
    "slate": {
        "bg": "#0f172a",
        "ink": "#93c5fd",
        "accent": "#60a5fa",
    },
    "sand": {
        "bg": "#f1f5f9",
        "ink": "#0f172a",
        "accent": "#64748b",
    },
}


def generate_sketch_svg(prompt: str, width: int, height: int, seed: Optional[int], theme: str) -> str:
    rnd = rng(seed or abs(hash(prompt)) % (2**32))
    palette = THEMES.get(theme, THEMES["slate"])
    ink = palette["ink"]
    accent = palette["accent"]

    # Parse prompt into tokens
    p = prompt.lower()
    wants_header = any(k in p for k in ["header", "title", "navbar", "hero"])
    wants_list = any(k in p for k in ["list", "items", "menu", "sidebar"])
    wants_form = any(k in p for k in ["form", "input", "search", "login", "button"])
    wants_cards = any(k in p for k in ["cards", "grid", "gallery", "images", "thumbnails", "card"])
    wants_chart = any(k in p for k in ["chart", "graph", "analytics"])
    wants_avatar = any(k in p for k in ["avatar", "profile", "user"])

    # Base SVG
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{palette["bg"]}"/>',
    ]

    y = 24
    margin = 24
    inner_w = width - margin * 2

    # Header
    if wants_header:
        parts.append(rough_rect(rnd, margin, y, inner_w, 60, stroke=ink, fill=accent))
        parts.append(text_el(margin + 16, y + 36, "Header / Title", ink))
        y += 80

    # Avatar block
    if wants_avatar:
        parts.append(rough_circle(rnd, margin + 32, y + 32, 24, stroke=ink, fill=accent))
        parts.append(text_el(margin + 72, y + 38, "User Name", ink))
        y += 72

    # Form block
    if wants_form:
        parts.append(rough_rect(rnd, margin, y, inner_w, 120, stroke=ink, fill=accent))
        parts.append(text_el(margin + 16, y + 28, "Input", ink))
        parts.append(rough_rect(rnd, margin + 12, y + 40, inner_w - 24, 28, stroke=ink))
        parts.append(text_el(margin + 16, y + 80, "Button", ink))
        parts.append(rough_rect(rnd, margin + 12, y + 90, 120, 28, stroke=ink, fill=accent))
        y += 140

    # Cards/Grid
    if wants_cards:
        cols = 3
        gap = 14
        cw = (inner_w - gap * (cols - 1)) / cols
        ch = 100
        for r in range(2):
            for c in range(cols):
                x = margin + c * (cw + gap)
                parts.append(rough_rect(rnd, x, y, cw, ch, stroke=ink))
                parts.append(text_el(x + 10, y + 24, f"Card {r*cols + c + 1}", ink))
            y += ch + gap
        y += 8

    # List / Sidebar
    if wants_list:
        lh = 28
        parts.append(rough_rect(rnd, margin, y, inner_w, lh * 5 + 20, stroke=ink))
        for i in range(5):
            parts.append(text_el(margin + 16, y + 24 + i * lh, f"List item {i+1}", ink))
            parts.append(rough_line(rnd, margin + 10, y + 30 + i * lh, margin + inner_w - 10, y + 30 + i * lh, ink))
        y += lh * 5 + 40

    # Chart
    if wants_chart:
        ch = 160
        parts.append(rough_rect(rnd, margin, y, inner_w, ch, stroke=ink))
        # bars
        bars = 6
        bw = inner_w / (bars * 1.5)
        for i in range(bars):
            bar_h = rnd.randint(40, ch - 30)
            bx = margin + 20 + i * (bw * 1.5)
            by = y + ch - bar_h - 10
            parts.append(rough_rect(rnd, bx, by, bw, bar_h, stroke=accent, fill=accent))
        y += ch + 20

    # Fallback content if prompt didn't specify
    if not (wants_header or wants_list or wants_form or wants_cards or wants_chart or wants_avatar):
        parts.append(rough_rect(rnd, margin, y, inner_w, 60, stroke=ink, fill=accent))
        parts.append(text_el(margin + 16, y + 36, "Title", ink))
        y += 80
        parts.append(rough_rect(rnd, margin, y, inner_w, 160, stroke=ink))
        parts.append(text_el(margin + 16, y + 40, "Your sketch will appear here", ink))

    parts.append(text_el(margin, height - 12, f'Prompt: {prompt[:80]}', ink))

    parts.append('</svg>')
    return "\n".join(parts)


@app.post("/api/sketch")
def make_sketch(req: PromptRequest):
    svg = generate_sketch_svg(req.prompt, req.width, req.height, req.seed, req.theme)
    return {"svg": svg}


@app.get("/api/sketch.svg")
def make_sketch_svg(prompt: str = Query(...), width: int = 800, height: int = 500, seed: Optional[int] = None, theme: str = "slate"):
    svg = generate_sketch_svg(prompt, width, height, seed, theme)
    return Response(content=svg, media_type="image/svg+xml")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
