from fastapi import APIRouter, Request, HTTPException,Depends
from fastapi.responses import Response
import httpx, json
from ..api import router
from ..vo.sub_vo import SubsCreatModel,SubsUpdateModel
from ..service.subs_service import SubsService

# clash_admin/api/subscriptions.py

# router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

@router.get("/subscriptions")
def list_subscriptions():
    return SubsService.get_subs()

@router.post("/subscriptions")
def create_subscription(
    data: SubsCreatModel,
    user=Depends(get_current_user)
):
    return SubsService.create_sub(data, user)


@router.put("/subscriptions/{sub_id}")
def update_subscription(
    data: SubsUpdateModel,
    user=Depends(get_current_user)
):
    return SubsService.update_sub(data, user)


@router.delete("/subscriptions/{sub_id}")
def delete_subscription(sub_id: str,
                        user=Depends(get_current_user)
                        ):
    SubsService.assert_not_bound(sub_id)
    SubsService.delete_sub(sub_id)
    return {"ok": True}
