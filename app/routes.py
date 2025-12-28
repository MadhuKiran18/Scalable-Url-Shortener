from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from .models import URL
from .utils import generate_short_code
from datetime import datetime, timedelta
from .cache import redis_client
from .schemas import ShortenRequest

router = APIRouter()

URL.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/shorten")
def shorten_url(
    request: ShortenRequest,
    db: Session = Depends(get_db)
):
    short_code = generate_short_code()
    expires_at = datetime.utcnow() + timedelta(minutes=request.expire_minutes)

    url = URL(
        original_url=str(request.original_url),
        short_code=short_code,
        expires_at=expires_at
    )

    db.add(url)
    db.commit()
    db.refresh(url)

    # Cache with TTL
    ttl = request.expire_minutes * 60
    redis_client.setex(short_code, ttl, str(request.original_url))

    return {
        "short_url": f"http://127.0.0.1:8000/{short_code}",
        "expires_at": expires_at
    }

@router.get("/{short_code}")
def redirect(short_code: str, db: Session = Depends(get_db)):
    url = db.query(URL).filter(URL.short_code == short_code).first()

    if not url:
        raise HTTPException(status_code=404, detail="URL not found")

    return RedirectResponse(url.original_url)
@router.get("/{short_code}")
def redirect(short_code: str, db: Session = Depends(get_db)):

    
    cached_url = redis_client.get(short_code)
    if cached_url:
        redis_client.incr(f"{short_code}:clicks")
        return {"original_url": cached_url, "source": "cache"}

    
    url = db.query(URL).filter(URL.short_code == short_code).first()
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")

    
    if url.expires_at and datetime.utcnow() > url.expires_at:
        raise HTTPException(status_code=410, detail="URL has expired")

    
    url.clicks += 1
    url.last_accessed = datetime.utcnow()
    db.commit()

   
    remaining_ttl = int((url.expires_at - datetime.utcnow()).total_seconds())
    if remaining_ttl > 0:
        redis_client.setex(short_code, remaining_ttl, url.original_url)

    return {"original_url": url.original_url, "source": "database"}
@router.get("/analytics/{short_code}")
def analytics(short_code: str, db: Session = Depends(get_db)):

    clicks = redis_client.get(f"{short_code}:clicks")
    last_accessed = redis_client.get(f"{short_code}:last")

    if clicks is not None:
        return {
            "short_code": short_code,
            "clicks": int(clicks),
            "last_accessed": last_accessed,
            "source": "cache"
        }

    # Fallback to DB
    url = db.query(URL).filter(URL.short_code == short_code).first()
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")

    return {
        "short_code": short_code,
        "clicks": url.clicks,
        "last_accessed": url.last_accessed,
        "source": "database"
    }