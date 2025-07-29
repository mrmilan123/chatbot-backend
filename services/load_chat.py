from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import asyncio
import os
from typing import Dict, List
from src.main_logger import logger
# from library.firebase_connect import firestore_client

ws_connections: Dict[str, List[WebSocket]] = {}


# async def websocket_endpoint(websocket: WebSocket, session_id: str):
#     await websocket.accept()

#     if session_id not in ws_connections:
#         ws_connections[session_id] = []

#     ws_connections[session_id].append(websocket)

#     user_collection = firestore_client.collection(session_id)


#     def on_snapshot(col_snapshot, changes, read_time):
#         for change in changes:
#             if change.type.name in ("ADDED", "MODIFIED"):
#                 data = change.document.to_dict()
#                 asyncio.create_task(broadcast(session_id, json.dumps(data)))

#     # Start watching the collection
#     query_watch = user_collection.on_snapshot(on_snapshot)

#     try:
#         while True:
#             await websocket.receive_text()  # Keep connection alive
#     except WebSocketDisconnect:
#         ws_connections[session_id].remove(websocket)


# async def broadcast(user_id: str, message: str):
#     for ws in ws_connections.get(user_id, []):
#         try:
#             await ws.send_text(message)
#         except:
#             logger.exception("error sending ws response")