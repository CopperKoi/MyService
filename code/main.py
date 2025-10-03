import os
import re
import shutil
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()  # load .env in project root

# 配置（从 .env 读取）
CONTENT_DIR = os.getenv("CONTENT_DIR", "./content")
os.makedirs(CONTENT_DIR, exist_ok=True)
JWT_SECRET = os.getenv("JWT_SECRET", "change_this_secret")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
ACCESS_EXPIRE_MINUTES = int(os.getenv("ACCESS_EXPIRE_MINUTES", "60"))
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "changeme")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")  # 可以是逗号分隔的列表

app = FastAPI(title="Markdown Blog (Minimal)")

# CORS
if CORS_ORIGINS == "*" or not CORS_ORIGINS:
    origins = ["*"]
else:
    origins = [o.strip() for o in CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# helper: slugify
_slug_re = re.compile(r"[^\w\-]+", re.UNICODE)
def slugify(text: str) -> str:
    s = text.strip().lower()
    s = s.replace(" ", "-")
    s = _slug_re.sub("-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")

# JWT helpers
def create_token(subject: str, expire_minutes: int = ACCESS_EXPIRE_MINUTES):
    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    data = {"sub": subject, "exp": expire.isoformat()}
    token = jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGO)
    return token

def verify_token_from_header(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid Authorization header")
    token = parts[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(401, "Invalid token payload")
        return sub
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

# Models
class PostListItem(BaseModel):
    slug: str
    title: str
    created_at: str

class PostDetail(BaseModel):
    slug: str
    title: str
    content: str
    created_at: str

# util: read title from markdown (first heading) or filename
def read_title_and_content(path: str):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    title = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break
        if line.startswith("#"):
            # fallback to first heading
            title = line.lstrip("#").strip()
            break
    return title or "", text

# API endpoints

@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username != ADMIN_USER or password != ADMIN_PASS:
        raise HTTPException(401, "Invalid credentials")
    token = create_token(username)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/posts", response_model=List[PostListItem])
def list_posts():
    items = []
    for fn in sorted(os.listdir(CONTENT_DIR), reverse=True):
        if not fn.lower().endswith(".md"):
            continue
        path = os.path.join(CONTENT_DIR, fn)
        slug = os.path.splitext(fn)[0]
        title, _ = read_title_and_content(path)
        st = os.stat(path)
        created_at = datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z"
        items.append(PostListItem(slug=slug, title=title or slug, created_at=created_at))
    return items

@app.get("/api/posts/{slug}", response_model=PostDetail)
def get_post(slug: str):
    safe = slugify(slug)
    path = os.path.join(CONTENT_DIR, f"{safe}.md")
    if not os.path.exists(path):
        raise HTTPException(404, "Not found")
    title, content = read_title_and_content(path)
    st = os.stat(path)
    created_at = datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z"
    return PostDetail(slug=safe, title=title or safe, content=content, created_at=created_at)

@app.post("/api/upload")
async def upload_md(file: UploadFile = File(...), user: str = Depends(verify_token_from_header)):
    # only allow .md
    filename = file.filename or "post.md"
    if not filename.lower().endswith(".md"):
        raise HTTPException(400, "Only .md files allowed")
    # read content
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 encoded markdown")
    # try read title for slug
    first_line = None
    for line in content.splitlines():
        if line.strip():
            first_line = line.strip()
            break
    if first_line and (first_line.startswith("#") or len(first_line) < 80):
        candidate = re.sub(r"^#+\s*", "", first_line)
    else:
        candidate = os.path.splitext(filename)[0]
    slug = slugify(candidate)
    if not slug:
        slug = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    out_path = os.path.join(CONTENT_DIR, f"{slug}.md")
    # if exists, append suffix
    i = 1
    base_slug = slug
    while os.path.exists(out_path):
        slug = f"{base_slug}-{i}"
        out_path = os.path.join(CONTENT_DIR, f"{slug}.md")
        i += 1
    # write file
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "slug": slug, "path": f"/api/posts/{slug}"}

@app.post("/api/posts")
def create_post(title: str = Form(...), content: str = Form(...), published: Optional[bool] = Form(False), user: str = Depends(verify_token_from_header)):
    # create slug from title
    slug = slugify(title or datetime.utcnow().isoformat())
    if not slug:
        slug = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    out_path = os.path.join(CONTENT_DIR, f"{slug}.md")
    i = 1
    base_slug = slug
    while os.path.exists(out_path):
        slug = f"{base_slug}-{i}"; out_path = os.path.join(CONTENT_DIR, f"{slug}.md"); i += 1
    # build markdown: if title not already as h1, prepend
    md = content
    if not content.lstrip().startswith("#"):
        md = f"# {title}\n\n{content}"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return {"ok": True, "slug": slug, "path": f"/api/posts/{slug}"}

# optional: mount content dir as static (raw .md files) if you prefer direct access
# app.mount("/raw", StaticFiles(directory=CONTENT_DIR), name="raw")

# root health
@app.get("/api/health")
def health():
    return {"status": "ok"}
