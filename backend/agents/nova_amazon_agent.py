import os
from dotenv import load_dotenv
from nova_act import NovaAct
from typing import Dict, Optional

load_dotenv()


def update_amazon_address(
    address: Dict[str, str],
    user_data_dir: Optional[str] = None,
    require_login: bool = True
) -> Dict[str, any]:
    """
    Update Amazon shipping address using NovaAct automation.
    
    Args:
        address: Dictionary containing address details:
            - country: str (e.g., "United States")
            - full_name: str (e.g., "John Doe")
            - phone: str (e.g., "+16693607809")
            - street: str (e.g., "55 S 5rd St")
            - unit: str (optional, e.g., "Apt 555")
            - city: str (e.g., "San Jose")
            - state: str (2-letter code, e.g., "CA")
            - zip: str (e.g., "95113")
            - make_default: bool (optional, default True)
        user_data_dir: Optional path to browser profile directory
        require_login: If True, prompts user to login before proceeding
    
    Returns:
        Dict with keys:
            - success: bool
            - data: Dict with step results and final address card text
            - error: Optional error message
    """
    # Set defaults
    if user_data_dir is None:
        user_data_dir = os.getenv("NOVA_USER_DATA_DIR", "/tmp/nova_profile")
    
    os.makedirs(user_data_dir, exist_ok=True)
    
    # Set default for make_default if not provided
    if "make_default" not in address:
        address["make_default"] = True
    
    # Set default for unit if not provided
    if "unit" not in address:
        address["unit"] = ""
    
    try:
        with NovaAct(
            starting_page="https://www.amazon.com",
            # user_data_dir=user_data_dir, 
            clone_user_data_dir=False,
            headless=False,
        ) as nova:
            if require_login:
                input("Log in to Amazon in the opened browser, then press Enter to continue...")

            # 1) Open Account & Lists (Your Account)
            step1 = nova.act("""
            If not already on amazon.com, go to https://www.amazon.com.
            Click the header item with id 'nav-link-accountList' (label typically 'Hello, … Account & Lists').
            Wait until a page loads with a main heading that contains 'Your Account'.
            Return 'account-ok' if you see it, otherwise return 'account-fail'.
            """)
            print("Step 1:", step1)

            # 2) Go to "Your Addresses"
            step2 = nova.act("""
            On the 'Your Account' page, click the card or link titled 'Your Addresses'.
            Wait for the addresses page (heading contains 'Your Addresses' or URL contains '/a/addresses').
            Return 'addresses-ok' if visible, else 'addresses-fail'.
            """)
            print("Step 2:", step2)

            # 3) Click "Add Address"
            step3 = nova.act("""
            On the addresses page, click the card or button labeled 'Add Address' (sometimes 'Add address').
            Wait for the 'Add a new address' form to appear (heading contains 'Add a new address' or URL contains '/a/addresses/add').
            Return 'form-ok' if the form is visible, else 'form-fail'.
            """)
            print("Step 3:", step3)

            # 4) Fill the address form (but don't submit yet)
            step4 = nova.act(f"""
            On the 'Add a new address' form:
            - If there is a 'Country/Region' dropdown, select "{address['country']}".
            - In 'Full name (First and Last name)' enter "{address['full_name']}" (clear any prefilled value first).
            - In 'Phone number' enter "{address['phone']}".
            - In 'Street address' (or 'Address line 1') enter "{address['street']}".
            - In 'Unit or suite number' (or 'Address line 2') enter "{address['unit']}".
            - In 'City' enter "{address['city']}".
            - In the 'State' dropdown, choose "{address['state']}".
            - In 'ZIP Code' enter "{address['zip']}".
            - {"Check the checkbox labeled 'Make this my default address'." if address["make_default"] else "Leave the 'Make this my default address' box unchecked."}
            Do NOT submit yet. Return 'filled' once all fields show the values above.
            """)
            print("Step 4:", step4)

            # 5) Submit the form
            step5 = nova.act("""
            Click the primary submit button at the bottom, labeled 'Add address' or 'Save address'.
            If an address verification modal or page appears:
              - Click its primary action like 'Use this address', 'Continue', or 'Continue without changes'.
              - Wait until you're back on the addresses list.
            Once returned to the addresses list, wait for an address card containing the newly entered street or ZIP to appear.
            Return 'submit-ok' if the new address card is visible, else 'submit-fail'.
            """)
            print("Step 5:", step5)

            # 6) Ensure it's the default (if checkbox didn't stick)
            step6 = nova.act(f"""
            On the addresses list page:
              - Locate the address card that contains "{address['street']}" or "{address['zip']}".
              - If it's not marked as Default and there's a 'Set as Default' link/button, click it.
              - Wait for the 'Default' badge to appear on that card.
            Return 'default-ok' if the card has the Default badge (or checkbox already made it default), else 'default-missing'.
            """)
            print("Step 6:", step6)

            # 7) Final confirmation (optional detail)
            final = nova.act(f"""
            Find the address card that contains "{address['street']}".
            Return its full visible text (name, street, city/state/zip, and any 'Default' badge) so we can confirm.
            """)
            print("Added Address Card:\n", final)
            
            return {
                "success": True,
                "data": {
                    "step1": step1,
                    "step2": step2,
                    "step3": step3,
                    "step4": step4,
                    "step5": step5,
                    "step6": step6,
                    "final_address": final
                },
                "error": None
            }
    
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": str(e)
        }


# Example usage / CLI entry point
if __name__ == "__main__":
    # Example address configuration
    ADDRESS = {
        "country": "United States",
        "full_name": "indraneel sarode",
        "phone": "+16693607809",
        "street": "55 S 5rd St",
        "unit": "Apt 555",
        "city": "San Jose",
        "state": "CA",
        "zip": "95113",
        "make_default": True,
    }
    
    result = update_amazon_address(ADDRESS)
    
    if result["success"]:
        print("\n✅ Address update completed successfully!")
        print(f"Final address card: {result['data']['final_address']}")
    else:
        print(f"\n❌ Address update failed: {result['error']}")
