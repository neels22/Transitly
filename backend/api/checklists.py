from datetime import datetime
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import checklists_table, moves_table
from core.security import get_current_user
from services.checklists import save_checklist_to_db


router = APIRouter(tags=["checklists"])


@router.get("/checklists")
def get_checklists(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user.get("sub")
        moves_resp = moves_table.query(
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,
        )
        moves = moves_resp.get("Items", [])
        if not moves:
            return {"checklists": []}

        aggregated: List[Dict[str, Any]] = []
        for move in moves:
            move_id = move.get("moveId")
            if not move_id:
                continue
            cl_resp = checklists_table.scan(
                FilterExpression="moveId = :mid",
                ExpressionAttributeValues={":mid": move_id},
            )
            items = cl_resp.get("Items", [])
            checklist = [
                {
                    "title": i.get("title", ""),
                    "status": i.get("status", "todo"),
                    "checklistId": i.get("checklistId", ""),
                    "agent_label": i.get("agent_label"),
                    "detail": i.get("detail", ""),
                }
                for i in items
            ]
            aggregated.append(
                {
                    "checklistId": move_id,
                    "createdAt": move.get("createdAt", datetime.utcnow().isoformat()),
                    "fromAddress": move.get("fromAddress", ""),
                    "toAddress": move.get("toAddress", ""),
                    "moveOutDate": move.get("moveOutDate", ""),
                    "moveInDate": move.get("moveInDate", ""),
                    "checklist": checklist,
                }
            )
        return {"checklists": aggregated}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"DynamoDB error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load checklists: {str(e)}")


class SaveChecklistRequest(BaseModel):
    checklist: List[Dict[str, Any]]
    move_id: Optional[str] = None


@router.post("/save-checklist")
def save_checklist(data: SaveChecklistRequest, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user.get("sub")
        if not data.checklist:
            raise HTTPException(status_code=400, detail="Checklist cannot be empty")

        current_time = datetime.utcnow()
        timestamp_str = current_time.strftime("%Y%m%d_%H%M%S")
        new_move_id = f"{user_id}#{timestamp_str}"

        move_data: Dict[str, Any] = {}
        if data.move_id:
            response = moves_table.query(
                KeyConditionExpression="userId = :uid AND moveId = :mid",
                ExpressionAttributeValues={":uid": user_id, ":mid": data.move_id},
            )
            if response.get("Items"):
                move = response["Items"][0]
                move_data = {
                    "fromAddress": move.get("fromAddress", ""),
                    "toAddress": move.get("toAddress", ""),
                    "moveOutDate": move.get("moveOutDate", ""),
                    "moveInDate": move.get("moveInDate", ""),
                }
        else:
            response = moves_table.query(
                KeyConditionExpression="userId = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,
                Limit=1,
            )
            if response.get("Items"):
                move = response["Items"][0]
                move_data = {
                    "fromAddress": move.get("fromAddress", ""),
                    "toAddress": move.get("toAddress", ""),
                    "moveOutDate": move.get("moveOutDate", ""),
                    "moveInDate": move.get("moveInDate", ""),
                }

        new_move_record = {
            "userId": user_id,
            "moveId": new_move_id,
            "fromAddress": move_data.get("fromAddress", ""),
            "toAddress": move_data.get("toAddress", ""),
            "moveOutDate": move_data.get("moveOutDate", ""),
            "moveInDate": move_data.get("moveInDate", ""),
            "createdAt": current_time.isoformat(),
            "updatedAt": current_time.isoformat(),
        }
        moves_table.put_item(Item=new_move_record)

        saved_result = save_checklist_to_db(user_id, new_move_id, data.checklist, move_data)
        return {
            "message": "Checklist saved successfully as new record",
            "move_id": new_move_id,
            "items_saved": saved_result.get("count", 0),
            "saved_at": current_time.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save checklist: {str(e)}")


class UpdateChecklistStatusRequest(BaseModel):
    checklist_id: str
    status: str


@router.post("/update-checklist-status")
def update_checklist_status(
    data: UpdateChecklistStatusRequest, current_user: dict = Depends(get_current_user)
):
    try:
        if data.status not in ["todo", "manualdone"]:
            raise HTTPException(status_code=400, detail="Status must be 'todo' or 'manualdone'")

        response = checklists_table.update_item(
            Key={"checklistId": data.checklist_id},
            UpdateExpression="SET #status = :status, updatedAt = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": data.status,
                ":updated_at": datetime.utcnow().isoformat(),
            },
            ReturnValues="ALL_NEW",
        )
        updated_item = response.get("Attributes", {})
        return {
            "message": "Checklist item status updated successfully",
            "checklist_id": data.checklist_id,
            "status": data.status,
            "updated_at": updated_item.get("updatedAt"),
        }
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            raise HTTPException(
                status_code=404, detail=f"Checklist item not found: {data.checklist_id}"
            )
        raise HTTPException(status_code=500, detail=f"Failed to update checklist item: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update checklist status: {str(e)}")


