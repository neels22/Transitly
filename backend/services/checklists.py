from datetime import datetime
from typing import Any, Dict, List

from core.config import checklists_table


def save_checklist_to_db(
    user_id: str,
    move_id: str,
    checklist: List[Dict[str, Any]],
    move_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Save generated checklist to TransitlyChecklists table.

    Returns a summary with saved items and count.
    """
    saved_items: List[Dict[str, Any]] = []
    try:
        for idx, item in enumerate(checklist):
            checklist_id = f"{move_id}#cl{idx + 1}"

            checklist_item = {
                "checklistId": checklist_id,
                "moveId": move_id,
                "title": item.get("title", ""),
                "status": item.get("status", "todo"),
                "agent_label": item.get("agent_label"),
                "detail": item.get("detail", ""),
                "createdAt": datetime.utcnow().isoformat(),
                "updatedAt": datetime.utcnow().isoformat(),
            }

            checklists_table.put_item(Item=checklist_item)
            saved_items.append(checklist_item)

        print(f"[Backend] Successfully saved {len(saved_items)} checklist items")
        return {"items": saved_items, "count": len(saved_items)}

    except Exception as e:
        print(f"Failed to save checklist to database: {str(e)}")
        raise


