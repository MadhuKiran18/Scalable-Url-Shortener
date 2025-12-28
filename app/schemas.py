from pydantic import BaseModel, HttpUrl

class ShortenRequest(BaseModel):
    original_url: HttpUrl
    expire_minutes: int = 60