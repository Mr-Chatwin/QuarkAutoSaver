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
async def search(req: SearchRequest):
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, processor.process_query, req.query)
    return {"results": results}

@app.post("/api/save")
async def save(req: SaveRequest):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, processor.save_and_rename, req.shareurl, req.media_info)
    return {"message": result}

@app.get("/")
def read_root():
    return {"message": "Quark Auto Saver is running. Bot is active in background."}
