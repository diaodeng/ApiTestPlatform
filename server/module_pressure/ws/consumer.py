# app/pressure/ws/consumer.py
import json
import asyncio
from redis.asyncio import Redis
from module_pressure.ws.manager import ws_manager

redis = Redis(host="redis", port=6379, decode_responses=True)

async def consume_pressure_events():
    last_id = "0-0"
    while True:
        streams = await redis.xread(
            streams={"pressure:events:*": last_id},
            block=5000,
            count=10
        )
        for stream, messages in streams:
            job_id = int(stream.split(":")[-1])
            for msg_id, fields in messages:
                last_id = msg_id
                await ws_manager.broadcast(
                    job_id,
                    {
                        "type": fields["type"],
                        "timestamp": fields["timestamp"],
                        "payload": json.loads(fields["payload"]),
                    }
                )
