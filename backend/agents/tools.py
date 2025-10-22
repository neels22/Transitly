import boto3
import os
from botocore.exceptions import ClientError
from langchain_core.tools import tool
from typing import Dict, Any, Optional
from agents.nova_amazon_agent import update_amazon_address as nova_update_amazon  # This file is in backend/, not agents/

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
DDB_TABLE = os.environ.get("DDB_TABLE", "TransitlyUsers")
DDB_MOVES_TABLE = os.environ.get("DDB_MOVES_TABLE", "TransitlyMoves")
DDB_CHECKLISTS_TABLE = os.environ.get("DDB_CHECKLISTS_TABLE", "TransitlyChecklists")

boto_kwargs = {"region_name": AWS_REGION}
if DYNAMODB_ENDPOINT:
    boto_kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
dynamodb = boto3.resource("dynamodb", **boto_kwargs)
users_table = dynamodb.Table(DDB_TABLE)
moves_table = dynamodb.Table(DDB_MOVES_TABLE)
checklists_table = dynamodb.Table(DDB_CHECKLISTS_TABLE)

@tool
def get_user_details(user_id: str) -> Dict[str, Any]:
    """
    Fetch user details from DynamoDB (user info + latest move details)
    Args:
        user_id: The ID of the user to fetch details for
    Returns:
        A dictionary containing the user details and move information
    """
    try:
        # 1. Get user info from TransitlyUsers table
        user_response = users_table.get_item(Key={"userId": user_id})
        user_data = user_response.get("Item", {})
        
        if not user_data:
            return {"_error": f"User {user_id} not found"}
        
        # 2. Get latest move info from TransitlyMoves table
        moves_response = moves_table.query(
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,  # Most recent first
            Limit=1
        )
        
        move_data = {}
        if moves_response.get("Items"):
            move = moves_response["Items"][0]
            move_data = {
                "from_address": move.get("fromAddress", ""),
                "to_address": move.get("toAddress", ""),
                "moving_date": move.get("moveInDate", ""),
                "moving_out_date": move.get("moveOutDate", "")
            }
        
        # 3. Combine user and move data
        return {
            "name": user_data.get("name", ""),
            "email": user_data.get("email", ""),
            "phone": user_data.get("phone", ""),
            **move_data
        }
        
    except ClientError as e:
        return {"_error": f"Database error: {str(e)}"}
    except Exception as e:
        return {"_error": f"Unexpected error: {str(e)}"}


@tool("update_amazon_address")
def update_amazon_address(
    full_name: str,
    street: str,
    city: str,
    state: str,
    zip_code: str,
    phone: str,
    country: str = "United States",
    unit: str = "",
    make_default: bool = True,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update the Amazon shipping address for a user using browser automation.
    
    Args:
        full_name: Full name (First and Last name)
        street: Street address
        city: City name
        state: State (2-letter code, e.g., "CA")
        zip_code: ZIP code
        phone: Phone number (e.g., "+16693607809")
        country: Country name (default: "United States")
        unit: Unit or apartment number (optional)
        make_default: Whether to set as default address (default: True)
        user_id: Optional user ID for tracking
    
    Returns:
        A dictionary with: { success: bool, address: str, error: str|None }
    """
    # Build address dictionary for nova function
    address_data = {
        "country": country,
        "full_name": full_name,
        "phone": phone,
        "street": street,
        "unit": unit,
        "city": city,
        "state": state,
        "zip": zip_code,
        "make_default": make_default,
    }
    
    # Call the actual nova automation function
    result = nova_update_amazon(
        address=address_data,
        require_login=True  # Will prompt for login if needed
    )
    
    # Transform result to match expected tool output format
    if result["success"]:
        # Extract the address string for backward compatibility
        address_str = f"{street}, {city}, {state} {zip_code}"
        if unit:
            address_str = f"{street} {unit}, {city}, {state} {zip_code}"
        
        return {
            "success": True,
            "address": address_str,
            "error": None
        }
    else:
        return {
            "success": False,
            "address": None,
            "error": result["error"]
        }