from fastapi import FastAPI
from .routes import router

app = FastAPI(title="Scalable URL Shortener")

app.include_router(router)

@app.get("/")
def home():
    return {"message": "Scalable URL Shortener API running"}