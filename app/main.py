from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from app.services.processor import Processor
import asyncio
from app.bot.tg_bot import start_bot

app = FastAPI(title="Quark Auto Saver API")
processor = Processor()

class SearchRequest(BaseModel):
    query: str

class SaveRequest(BaseModel):
    shareurl: str
    media_info: dict

@app.on_event("startup")
async def startup_event():
    # Run bot in background
    asyncio.create_task(start_bot())

@app.post("/api/search")
def search(req: SearchRequest):
    results = processor.process_query(req.query)
    return {"results": results}

@app.post("/api/save")
def save(req: SaveRequest):
    result = processor.save_and_rename(req.shareurl, req.media_info)
    return {"message": result}

@app.get("/")
def read_root():
    return {"message": "Quark Auto Saver is running. Bot is active in background."}
