# app/pressure/ws/manager.py
from collections import defaultdict

class WSManager:
    def __init__(self):
        self.clients = defaultdict(set)

    async def connect(self, job_id, ws):
        await ws.accept()
        self.clients[job_id].add(ws)

    def disconnect(self, job_id, ws):
        self.clients[job_id].discard(ws)

    async def broadcast(self, job_id, message):
        for ws in list(self.clients[job_id]):
            await ws.send_json(message)

ws_manager = WSManager()
