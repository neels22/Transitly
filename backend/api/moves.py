from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import moves_table
from core.security import get_current_user


class MoveDetails(BaseModel):
    from_address: str
    to_address: str
    move_out_date: date
    move_in_date: date


router = APIRouter(tags=["moves"])


@router.post("/move")
def submit_move_details(data: MoveDetails, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub")
    move_item = {
        "userId": user_id,
        "moveId": f"{user_id}#{data.move_out_date}",
        "fromAddress": data.from_address,
        "toAddress": data.to_address,
        "moveOutDate": data.move_out_date.isoformat(),
        "moveInDate": data.move_in_date.isoformat(),
        "createdAt": date.today().isoformat(),
    }
    try:
        moves_table.put_item(Item=move_item)
        return {"message": "Move details saved successfully.", "data": move_item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save move: {str(e)}")


@router.delete("/move/{move_id}")
def delete_move_and_checklist(move_id: str, current_user: dict = Depends(get_current_user)):
    from botocore.exceptions import ClientError
    from core.config import checklists_table

    user_id = current_user.get("sub")
    try:
        moves_table.delete_item(
            Key={"userId": user_id, "moveId": move_id},
            ConditionExpression="attribute_exists(moveId)",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise HTTPException(status_code=404, detail="Move not found")
        raise HTTPException(status_code=500, detail=f"Failed to delete move: {str(e)}")

    try:
        cl_resp = checklists_table.scan(
            FilterExpression="moveId = :mid", ExpressionAttributeValues={":mid": move_id}
        )
        items = cl_resp.get("Items", [])
        if items:
            with checklists_table.batch_writer() as batch:
                for item in items:
                    checklist_pk = item.get("checklistId")
                    if checklist_pk:
                        batch.delete_item(Key={"checklistId": checklist_pk})
    except ClientError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete checklist items: {str(e)}"
        )

    return {
        "message": "Move and associated checklist items deleted successfully.",
        "moveId": move_id,
    }


