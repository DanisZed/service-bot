from fastapi import FastAPI
from app.api.max_webhook import router as max_router

app = FastAPI(title="Service Bot Backend")

app.include_router(max_router, prefix="/max", tags=["max"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
