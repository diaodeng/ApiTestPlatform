from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import Response
import httpx, json
from ..vo.clash_vo import ClashCreatModel, ClashUpdateModel
from ..api import router
from ..service.clash_service import ClashService

# router = APIRouter(prefix="/clash_server", tags=["Subscriptions"])

async def apply_subscription(service, subscription):
    content = fetch_subscription(subscription.url)
    config = render_clash_config(content)

    await ClashService.update_clash_config(config)


@router.get("/clashes")
def list_clashes():
    return load_json(CLASH_FILE)

@router.post("/clash")
def create_clash_service(
    data: ClashCreatModel,
    user=Depends(get_current_user)
):
    return ClashService.create_clash(data, user)


@router.put("/clash")
def update_clash_service(
    data: ClashUpdateModel,
    user=Depends(get_current_user)
):
    return ClashService.update_clash(data)


@router.delete("/clash/{service_id}")
def delete_clash_service(service_id: str):
    # ClashService.assert_no_running_task(clash_id=service_id)
    ClashService.delete_clash(service_id)


@router.post("/clash/{service_id}/bind-subscription")
def bind_subscription(
    service_id: str,
    sub_id: str,
    user=Depends(get_current_user)
):
    ClashService.bind_sub(service_id, sub_id)


