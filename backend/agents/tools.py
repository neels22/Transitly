from langchain_core.tools import tool
from typing import Dict, Any, Optional
from nova_amazon_agent import update_amazon_address as nova_update_amazon

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
        "phone": "+16693607809",
        "from_address": "123 Main St, Anytown, CA, 90210",
        "to_address": "456 Oak Ave, San Jose, CA, 95113",
        "moving_date": "2021-01-01",
        "moving_out_date": "2021-01-01"
    }

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