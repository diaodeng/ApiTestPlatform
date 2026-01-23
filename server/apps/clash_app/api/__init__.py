import json
import os
import subprocess

import httpx
from fastapi import HTTPException, APIRouter

router = APIRouter()

SUB_FILE = "../data/subscriptions.json"
CLASH_FILE = "../data/clashes.json"
PROFILE_DIR = "../data/profiles"


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ========== 切换订阅（核心功能） ==========
@router.post("/clash/{clash_id}/use/{sub_id}")
async def switch_subscription(clash_id: str, sub_id: str):
    subs = load_json(SUB_FILE)
    clashes = load_json(CLASH_FILE)

    if sub_id not in subs:
        raise HTTPException(404, "Subscription not found")
    if clash_id not in clashes:
        raise HTTPException(404, "Clash not found")

    clash = clashes[clash_id]
    profile_path = f"{PROFILE_DIR}/{sub_id}.yaml"
    current_path = clash["config"]

    if not os.path.exists(profile_path):
        raise HTTPException(500, "Profile not generated")

    # 1️⃣ 切换软链接
    subprocess.run(["ln", "-sf", os.path.abspath(profile_path), current_path], check=True)

    # 2️⃣ 调用 reload
    async with httpx.AsyncClient() as client:
        await client.put(
            f"{clash['api']}/configs",
            headers={"Authorization": f"Bearer {clash['secret']}"}
        )

    return {"status": "ok", "clash": clash_id, "subscription": sub_id}


@router.get("/clash/{clash_id}/yacd")
def get_yacd_url(clash_id: str):
    clashes = load_json(CLASH_FILE)
    if clash_id not in clashes:
        raise HTTPException(404)
    return {
        "url": f"/yacd?clash={clash_id}"
    }
