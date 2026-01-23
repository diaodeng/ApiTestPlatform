from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
import httpx, json

router = APIRouter()
CLASH_FILE = "clash_admin/data/clashes.json"

@router.api_route("/{clash_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_clash(clash_id: str, path: str, request: Request):
    with open(CLASH_FILE) as f:
        clashes = json.load(f)

    if clash_id not in clashes:
        raise HTTPException(404)

    clash = clashes[clash_id]

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            request.method,
            f"{clash['api']}/{path}",
            headers={
                "Authorization": f"Bearer {clash['secret']}"
            },
            content=await request.body()
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp.headers
    )


