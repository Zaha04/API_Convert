from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from io import BytesIO
from PIL import Image
import pillow_avif  # noqa: F401  # side-effect: enable AVIF in Pillow
import httpx
import re

app = FastAPI(title="AVIF Converter API", version="1.0.0")

# CORS: ajustează origin-urile după nevoie
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # pune aici domeniile tale dacă vrei restrictiv
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _to_avif_bytes(
    data: bytes,
    quality: int,
    lossless: bool,
    width: Optional[int],
    height: Optional[int],
) -> bytes:
    img = Image.open(BytesIO(data))
    # Păstrăm transparența dacă există (PNG → RGBA). Pentru JPEG e RGB.
    if img.mode in ("P", "LA"):
        img = img.convert("RGBA")
    elif img.mode not in ("RGB", "RGBA"):
        # convertim default la RGBA pentru siguranță
        img = img.convert("RGBA")

    # Resize opțional
    if width or height:
        # menține proporțiile dacă lipsește una dintre dimensiuni
        w, h = img.size
        target_w = width or int(w * (height / h))
        target_h = height or int(h * (width / w))
        img = img.resize((target_w, target_h), Image.LANCZOS)

    out = BytesIO()
    save_params = {"format": "AVIF"}
    if lossless:
        save_params["lossless"] = True
    else:
        save_params["quality"] = quality
    img.save(out, **save_params)
    out.seek(0)
    return out.read()

@app.post("/convert", summary="Convert uploaded JPG/PNG/WEBP to AVIF")
async def convert_file_to_avif(
    file: UploadFile = File(...),
    quality: int = Query(60, ge=1, le=100),
    lossless: bool = Query(False),
    width: Optional[int] = Query(None, ge=1),
    height: Optional[int] = Query(None, ge=1),
):
    if file.content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Only JPEG/JPG/PNG/WEBP are accepted.")
    try:
        data = await file.read()
        avif = _to_avif_bytes(data, quality, lossless, width, height)
        base = (file.filename or "image").rsplit(".", 1)[0]
        headers = {"Content-Disposition": f'attachment; filename="{base}.avif"'}
        return Response(content=avif, media_type="image/avif", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/convert-url", summary="Convert image by URL (JPG/PNG/WEBP) to AVIF")
async def convert_url_to_avif(
    url: str,
    quality: int = Query(60, ge=1, le=100),
    lossless: bool = Query(False),
    width: Optional[int] = Query(None, ge=1),
    height: Optional[int] = Query(None, ge=1),
    timeout: float = Query(20.0, ge=1.0, le=60.0),
):
    if not re.match(r"^https?://", url, flags=re.I):
        raise HTTPException(status_code=400, detail="Invalid URL.")
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
                # acceptăm totuși uneori fără header corect — încercăm
                pass
            avif = _to_avif_bytes(resp.content, quality, lossless, width, height)
            headers = {"Content-Disposition": 'attachment; filename="image.avif"'}
            return Response(content=avif, media_type="image/avif", headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", include_in_schema=False)
async def root():
    return {"ok": True, "service": "avif-converter", "version": "1.0.0"}
