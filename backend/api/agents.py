import asyncio
import json
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from agents.agent_state import ChecklistItem
from agents.orchestrator_agent import run_orchestrator_agent
from agents.config import Config
from core.config import moves_table
from core.security import get_current_user


router = APIRouter(tags=["agents"])


@router.get("/run-agents-stream")
async def run_agents_stream(current_user: dict = Depends(get_current_user)):
    async def event_generator():
        try:
            user_id = current_user.get("sub")
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Starting agents...'})}\n\n"
            await asyncio.sleep(0.1)

            user_details: Dict[str, Any] = {
                "name": current_user.get("name", ""),
                "email": current_user.get("email", ""),
                "phone": current_user.get("phone_number", ""),
            }
            try:
                response = moves_table.query(
                    KeyConditionExpression="userId = :uid",
                    ExpressionAttributeValues={":uid": user_id},
                    ScanIndexForward=False,
                    Limit=1,
                )
                if not response.get("Items"):
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No move found. Please submit move details first.'})}\n\n"
                    return
                move = response["Items"][0]
                user_details.update(
                    {
                        "from_address": move.get("fromAddress", ""),
                        "to_address": move.get("toAddress", ""),
                        "moving_date": move.get("moveInDate", ""),
                        "moving_out_date": move.get("moveOutDate", ""),
                    }
                )
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to fetch move details: {str(e)}'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'user_details', 'data': user_details})}\n\n"
            await asyncio.sleep(0.5)

            initial_state = {
                "messages": [],
                "user_id": user_id,
                "user_details": user_details,
                "checklist": [],
                "steps": 0,
                "done": False,
                "next_task": "",
                "reason": "",
            }

            yield f"data: {json.dumps({'type': 'status', 'message': 'Running agent workflow...'})}\n\n"
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, run_orchestrator_agent, initial_state
            )

            checklist_dicts: List[Dict[str, Any]] = []
            for item in result.get("checklist", []):
                if isinstance(item, ChecklistItem):
                    checklist_dicts.append(
                        {
                            "title": item.title,
                            "status": item.status,
                            "detail": item.detail,
                            "agent_label": item.agent_label,
                            "required_fields": item.required_fields,
                            "depends_on": item.depends_on,
                        }
                    )
                else:
                    checklist_dicts.append(item)

            yield f"data: {json.dumps({'type': 'checklist', 'data': checklist_dicts})}\n\n"
            await asyncio.sleep(0.5)

            yield f"data: {json.dumps({'type': 'complete', 'data': {'checklist': checklist_dicts, 'steps': result.get('steps', 0), 'address_change_result': result.get('address_change_result', {})}})}\n\n"
        except Exception as e:
            print(f"SSE Error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/run-agents")
def run_agents(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user.get("sub")
        user_details = {
            "name": current_user.get("name", ""),
            "email": current_user.get("email", ""),
            "phone": current_user.get("phone_number", ""),
        }
        try:
            response = moves_table.query(
                KeyConditionExpression="userId = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,
                Limit=1,
            )
            if response.get("Items"):
                move = response["Items"][0]
                user_details.update(
                    {
                        "from_address": move.get("fromAddress", ""),
                        "to_address": move.get("toAddress", ""),
                        "moving_date": move.get("moveInDate", ""),
                        "moving_out_date": move.get("moveOutDate", ""),
                    }
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail="No move found for user. Please submit move details first.",
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch move details: {str(e)}")

        initial_state = {
            "messages": [],
            "user_id": user_id,
            "user_details": user_details,
            "checklist": [],
            "steps": 0,
            "done": False,
            "next_task": "",
            "reason": "",
        }
        result = run_orchestrator_agent(initial_state)
        checklist_dicts: List[Dict[str, Any]] = []
        for item in result.get("checklist", []):
            if isinstance(item, ChecklistItem):
                checklist_dicts.append(
                    {
                        "title": item.title,
                        "status": item.status,
                        "detail": item.detail,
                        "agent_label": item.agent_label,
                        "required_fields": item.required_fields,
                        "depends_on": item.depends_on,
                    }
                )
            else:
                checklist_dicts.append(item)
        return {
            "message": "Agent workflow completed",
            "checklist": checklist_dicts,
            "steps": result.get("steps", 0),
            "done": result.get("done", False),
            "user_details": result.get("user_details", {}),
            "address_change_result": result.get("address_change_result", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent workflow failed: {str(e)}")


from typing import Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str
    checklist_context: Optional[List[Dict[str, Any]]] = None


@router.post("/chat")
async def chat_with_agent(data: ChatMessage, current_user: dict = Depends(get_current_user)):
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        user_id = current_user.get("sub")
        user_name = current_user.get("name", "").split()[0]

        response = moves_table.query(
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,
            Limit=1,
        )
        move_context = ""
        if response.get("Items"):
            move = response["Items"][0]
            move_context = f"""
User is moving:
- From: {move.get('fromAddress')}
- To: {move.get('toAddress')}
- Move out: {move.get('moveOutDate')}
- Move in: {move.get('moveInDate')}
"""

        checklist_context = ""
        if data.checklist_context:
            checklist_context = "\nCurrent checklist:\n" + "\n".join(
                [f"- {item['title']}: {item['status']}" for item in data.checklist_context]
            )

        system_prompt = f"""You are a helpful moving assistant for {user_name}.
You help with relocation tasks like updating addresses, transferring utilities, etc.

{move_context}
{checklist_context}

Be concise, helpful, and action-oriented. If the user asks about a task, 
explain what needs to be done and offer to help automate it if possible."""

        llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=data.message)]
        response = llm.invoke(messages)
        return {"message": response.content, "timestamp": date.today().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


