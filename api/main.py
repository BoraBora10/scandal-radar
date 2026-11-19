import asyncio
import json
import os
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from uuid import uuid4

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ingestion.build_demo import compile_demo
from ingestion.collector import Collector
from api.publish import publish

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
DB = ROOT / ".data" / "replay.sqlite"
DEMO = os.getenv("DEMO_MODE", "false").lower() == "true"
TAPE = compile_demo(set(CONFIG["alerts"]["levels"]))
INTERVAL = max(1.0, float(CONFIG["demo"]["interval_seconds"]))
SPEED = float(os.getenv("DEMO_SPEED", CONFIG["demo"]["speed"]))
if SPEED not in (0.5, 1, 2, 4):
    raise ValueError("DEMO_SPEED must be 0.5, 1, 2 or 4")


def save_frame(run: str, frame: int) -> None:
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute(
            "INSERT OR IGNORE INTO replay(run, frame, payload) VALUES(?, ?, ?)",
            (run, frame, json.dumps(TAPE["frames"][frame])),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS replay(run TEXT, frame INTEGER, payload TEXT, PRIMARY KEY(run, frame))"
        )
    collector = None if DEMO else Collector(ROOT)
    app.state.collector = collector
    publisher = None
    if collector:
        collector.start()
        if os.getenv("RADAR_SITE_URL"):
            publisher = asyncio.create_task(
                publish(
                    collector,
                    os.environ["RADAR_SITE_URL"],
                    os.environ["RADAR_SITE_TOKEN"],
                    os.environ["RADAR_WRITE_KEY"],
                )
            )
    try:
        yield
    finally:
        if publisher:
            publisher.cancel()
            await asyncio.gather(publisher, return_exceptions=True)
        if collector:
            await collector.close()


app = FastAPI(title="Scandal Radar", lifespan=lifespan)


@app.get("/")
async def dashboard() -> HTMLResponse:
    html = (ROOT / "dist" / "client" / "index.html").read_text()
    return HTMLResponse(
        html.replace(
            "<head>",
            '<head><meta name="radar-transport" content="websocket"><meta name="radar-mode" content="'
            + ("demo" if DEMO else "live")
            + '">',
        )
    )


@app.get("/api/live")
async def live():
    if not app.state.collector:
        return JSONResponse(
            {"error": "Live collection is disabled in DEMO_MODE."}, status_code=503
        )
    return JSONResponse(
        app.state.collector.snapshot(), headers={"Cache-Control": "no-store"}
    )


@app.get("/api/directory")
async def directory():
    from entities.directory import Directory

    value = app.state.collector.directory if app.state.collector else Directory()
    return value.data


@app.websocket("/ws/live")
async def live_stream(ws: WebSocket):
    await ws.accept()
    if not app.state.collector:
        await ws.close(1000)
        return
    try:
        while True:
            await ws.send_json(app.state.collector.snapshot())
            await asyncio.sleep(4)
    except (WebSocketDisconnect, RuntimeError, OSError):
        return


@app.websocket("/ws")
async def replay(ws: WebSocket) -> None:
    await ws.accept()
    frames = TAPE["frames"]
    index = TAPE["initial"]
    speed = SPEED
    run = uuid4().hex
    paused = False
    try:
        while True:
            await asyncio.to_thread(save_frame, run, index)
            ended = index == len(frames) - 1
            await ws.send_json(
                dict(
                    index=index,
                    frame=frames[index],
                    speed=speed,
                    paused=paused,
                    ended=ended,
                )
            )
            try:
                wait = None if paused or ended else INTERVAL / speed
                msg = await asyncio.wait_for(ws.receive_json(), timeout=wait)
            except asyncio.TimeoutError:
                index += 1
                continue
            if not isinstance(msg, dict):
                continue
            action = msg.get("action")
            if action == "replay":
                index, paused, run = 0, False, uuid4().hex
            elif action == "pause":
                paused = not paused
            elif action == "speed" and msg.get("value") in (0.5, 1, 2, 4):
                speed = msg["value"]
    except WebSocketDisconnect:
        return


app.mount("/", StaticFiles(directory=ROOT / "dist" / "client"), name="dashboard")
