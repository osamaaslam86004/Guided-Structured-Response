# routes/websocket_events.py

# This file contains the WebSocket endpoint for streaming task events to clients in real-time.


import asyncio
import json
import os

import redis.asyncio as redis

from fastapi import APIRouter, WebSocket
from fastapi import WebSocketDisconnect

router = APIRouter()


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


@router.websocket("/ws/events/{task_id}")
async def task_events(
    websocket: WebSocket,
    task_id: str,
):
    """
    Now your agent can connect once:

    ws://localhost:8000/ws/events/<task_id>
    and receive

    {
      "type": "TASK_STARTED",
      "task_id": "..."
    }
    """

    await websocket.accept()

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=3,
        decode_responses=True,
    )

    pubsub = client.pubsub()

    channel = f"task_events:{task_id}"

    await pubsub.subscribe(channel)

    try:

        while True:

            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )

            if message:

                data = json.loads(message["data"])

                await websocket.send_json(data)

                if data.get("type") in {"TASK_COMPLETED", "TASK_DEAD_LETTER"}:
                    break

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:

        pass

    finally:

        await pubsub.unsubscribe(channel)

        await pubsub.close()

        await client.close()
