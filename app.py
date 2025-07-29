from fastapi import FastAPI, Request, Body, WebSocket
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from src.main_logger import logger
from services.chat import router
from services.util_services import util_router

app = FastAPI()
IGNORE = ["/ping"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def check_session(request: Request, call_next):
    try:
        path = request.scope["path"]
        logger.info(f"request received  --> {path}")

        if request.method != "OPTIONS" and path not in IGNORE:
            session_id = request.headers.get("session_id")
            if not session_id:
                raise ValueError("Missing session_id header")
            logger.info(f"{session_id=}")
            request.state.session_id = session_id

        response = await call_next(request)
    except Exception as e:
        logger.exception(f"error in main middleware {e}")
        response = JSONResponse("Unauthorized", status_code=401)
    return response


# @app.websocket("/ws/{session_id}")
# async def ws_endpoint(websocket: WebSocket, session_id: str):
#     try:
#         await websocket_endpoint(websocket, session_id)
#     except Exception as e:
#         logger.exception(f"error in ws endpoint main {e}")

@app.get("/ping")
async def ping(request: Request):
    return {"message":"service is running"}


app.include_router(router)
app.include_router(util_router)
