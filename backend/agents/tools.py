from langchain_core.tools import tool
from typing import Dict, Any, Optional

# need a tool that will fetch user details from the database
# for now  create a dummy .sqlite or .db with random user data
# user data includes name, from address, to address, movin date, move out date

# then use the tool to fetch the user details
# the tool should return the user details in a dictionary
# the tool should be able to handle the user details in a dictionary


@tool
def get_user_details(user_id: str) -> Dict[str, Any]:
    """
    Fetch user details from the database
    Args:
        user_id: The ID of the user to fetch details for
    Returns:
        A dictionary containing the user details
    """

    return {
        "name": "John Doe",
        "from_address": "123 Main St, Anytown, USA",
        "to_address": "456 Main St, Anytown, USA",
        "moving_date": "2021-01-01",
        "moving_out_date": "2021-01-01"
    }

@tool("update_amazon_address")
def update_amazon_address(new_address: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Pretend to update the Amazon address for a user.
    Returns a shape your graph expects: { success, address, error? }.
    """
    # basic validation
    if not new_address or not new_address.strip():
        return {"success": False, "error": "New address is empty or whitespace."}

    # simulate a write (no real side effects in this dummy)
    updated = new_address.strip()

    # you could branch on user_id here if you wanted to simulate failures:
    # if user_id == "bad-user": return {"success": False, "error": "User not found."}

    return {"success": True, "address": updated}