# backend/main.py
import os
import json
import requests
from urllib.parse import urlencode
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Form, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import boto3
from botocore.exceptions import ClientError
from jose import JWTError, jwt
from jose.exceptions import JWKError
import base64
from datetime import date, datetime
from pydantic import BaseModel
import re
from dotenv import load_dotenv
from agents.orchestrator_agent import run_orchestrator_agent
from agents.agent_state import ChecklistItem
from typing import Optional, List
from fastapi.responses import StreamingResponse
import asyncio

load_dotenv()

app = FastAPI(title="Transitly Backend (dev with Docker)")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Load config from .env === 
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN")
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")  # Add this to .env if using confidential client
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:8000/auth/callback")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
DDB_TABLE = os.environ.get("DDB_TABLE", "TransitlyUsers")
DDB_MOVES_TABLE = os.environ.get("DDB_MOVES_TABLE", "TransitlyMoves")
DDB_CHECKLISTS_TABLE = os.environ.get("DDB_CHECKLISTS_TABLE", "TransitlyChecklists")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
USER_POOL_ID = os.environ.get("USER_POOL_ID")  # Add this to .env

# === Setup DynamoDB ===
boto_kwargs = {"region_name": AWS_REGION}
if DYNAMODB_ENDPOINT:
    boto_kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
dynamodb = boto3.resource("dynamodb", **boto_kwargs)
users_table = dynamodb.Table(DDB_TABLE)
moves_table = dynamodb.Table(DDB_MOVES_TABLE)
checklists_table = dynamodb.Table(DDB_CHECKLISTS_TABLE)

# === Setup Cognito client ===
cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)

# === Security ===
security = HTTPBearer()

# JWKS cache
_jwks_cache: Optional[Dict] = None

def format_phone_to_e164(phone: str) -> str:
    """
    Format phone number to E.164 format (+1XXXXXXXXXX)
    Strips all non-digit characters and prepends +1 for US numbers
    """
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's already prefixed with country code
    if digits_only.startswith('1') and len(digits_only) == 11:
        return f"+{digits_only}"
    elif len(digits_only) == 10:
        return f"+1{digits_only}"
    else:
        raise ValueError(f"Invalid phone number format. Expected 10 digits, got {len(digits_only)}")

def validate_phone_e164(phone: str) -> bool:
    """
    Validate that phone is in correct E.164 format for US numbers
    Format: +1XXXXXXXXXX (exactly 12 characters)
    """
    return bool(re.match(r'^\+1\d{10}$', phone))

def calculate_secret_hash(username: str) -> Optional[str]:
    """Calculate SECRET_HASH for Cognito operations"""
    if not CLIENT_SECRET:
        return None
    
    import hmac
    import hashlib
    
    message = username + CLIENT_ID
    secret_hash = base64.b64encode(
        hmac.new(
            CLIENT_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
    ).decode()
    
    return secret_hash

def get_jwks():
    """Get JWKS from AWS Cognito with caching"""
    global _jwks_cache
    if _jwks_cache is None:
        jwks_url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        try:
            response = requests.get(jwks_url)
            response.raise_for_status()
            _jwks_cache = response.json()
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch JWKS: {str(e)}")
    return _jwks_cache

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify JWT token from Cognito"""
    try:
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise HTTPException(status_code=401, detail="Invalid token: missing kid")
        
        # Get JWKS and find matching key
        jwks = get_jwks()
        key = None
        for k in jwks["keys"]:
            if k["kid"] == kid:
                key = k
                break
        
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token: key not found")
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current user from JWT token"""
    if not credentials.scheme == "Bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    
    payload = verify_jwt_token(credentials.credentials)
    return payload

def save_checklist_to_db(user_id: str, move_id: str, checklist: List[Dict[str, Any]], move_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save generated checklist to TransitlyChecklists table
    
    Args:
        user_id: User ID
        move_id: Move ID (userId#moveOutDate)
        checklist: List of checklist items
        move_data: Move details (from/to addresses, dates)
    
    Returns:
        The saved checklist item
    """
    
    checklist_item = {
        "userId": user_id,
        "moveId": move_id,
        "checklist": checklist,
        "fromAddress": move_data.get("fromAddress", ""),
        "toAddress": move_data.get("toAddress", ""),
        "moveOutDate": move_data.get("moveOutDate", ""),
        "moveInDate": move_data.get("moveInDate", ""),
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat()
    }
    
    try:
        checklists_table.put_item(Item=checklist_item)
        return checklist_item
    except Exception as e:
        print(f"Failed to save checklist to database: {str(e)}")
        raise

# --- MOVE DATA MODEL ---
class MoveDetails(BaseModel):
    from_address: str
    to_address: str
    move_out_date:date
    move_in_date: date

# === Routes ===
@app.get("/")
def root():
    return {"msg": "Transitly backend. Visit /signup or /login."}

# --- SIGNUP ---
@app.post("/signup")
def signup(
    email: str = Form(...), 
    password: str = Form(...), 
    first_name: str = Form(...), 
    last_name: str = Form(...), 
    username: str = Form(...),
    phone: str = Form(...)
):
    """Sign up a new user with AWS Cognito"""
    try:
        # Format and validate phone number
        try:
            formatted_phone = format_phone_to_e164(phone)
            if not validate_phone_e164(formatted_phone):
                raise ValueError("Invalid phone format after formatting")
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"Invalid phone number: {str(ve)}")
        
        user_attributes = [
            {"Name": "email", "Value": email},
            {"Name": "given_name", "Value": first_name},
            {"Name": "family_name", "Value": last_name},
            {"Name": "name", "Value": f"{first_name} {last_name}"},
            {"Name": "phone_number", "Value": formatted_phone}  # Add phone in E.164 format
        ]
        
        signup_params = {
            "ClientId": CLIENT_ID,
            "Username": username,
            "Password": password,
            "UserAttributes": user_attributes
        }
        
        secret_hash = calculate_secret_hash(username)
        if secret_hash:
            signup_params["SecretHash"] = secret_hash
        
        response = cognito_client.sign_up(**signup_params)

        # After successful signup, seed default move + checklist data
        try:
            user_sub = response.get("UserSub")
            if user_sub:

                # Insert TransitlyMoves record
                move_item1 = {
                    "userId": user_sub,
                    "fromAddress": "1234 Lane lane, Drive drive, San Jose, CA 987653",
                    "toAddress": "5678 Driveway driveway, San Mateo, CA 987654",
                    "moveOutDate": "2025-12-12",
                    "moveInDate": "2025-12-12",
                    "createdAt": "2025-10-20",
                }
                move_item2 = {
                    "userId": user_sub,
                    "fromAddress": "4321 Elm Street, Sunnyvale, CA 94085",
                    "toAddress": "8765 Oak Avenue, Palo Alto, CA 94303",
                    "moveOutDate": "2026-01-15",
                    "moveInDate": "2026-01-16",
                    "createdAt": "2025-10-21",
                }

                move_item3 = {
                    "userId": user_sub,
                    "fromAddress": "1010 Blossom Hill Rd, Los Gatos, CA 95032",
                    "toAddress": "2222 Shoreline Blvd, Mountain View, CA 94043",
                    "moveOutDate": "2025-11-05",
                    "moveInDate": "2025-11-06",
                    "createdAt": "2025-10-22",
                }
                # Compose deterministic moveId (userId#moveOutDate) and attach it
                move_item1_id = f"{user_sub}#{move_item1['moveOutDate']}"
                move_item1["moveId"] = move_item1_id
                move_item2_id = f"{user_sub}#{move_item2['moveOutDate']}"
                move_item2["moveId"] = move_item2_id
                move_item3_id = f"{user_sub}#{move_item3['moveOutDate']}"
                move_item3["moveId"] = move_item3_id
                try:
                    moves_table.put_item(Item=move_item1)
                    moves_table.put_item(Item=move_item2)
                    moves_table.put_item(Item=move_item3)
                except Exception as inner_e:
                    # Don't fail signup if seeding fails; just log
                    print(f"Failed to seed default move for {user_sub}: {str(inner_e)}")

                checklist_item1_1 = {
                    "checklistId": f"{move_item1_id}#cl1",
                    "moveId": move_item1_id,
                    "title": "To do A",
                    "status": "agentdone",
                }
                checklist_item1_2 = {
                    "checklistId": f"{move_item1_id}#cl2",
                    "moveId": move_item1_id,
                    "title": "To do B",
                    "status": "manualdone",
                }
                checklist_item1_3 = {
                    "checklistId": f"{move_item1_id}#cl3",
                    "moveId": move_item1_id,
                    "title": "To do C",
                    "status": "failed",
                }
                checklist_item1_4 = {
                    "checklistId": f"{move_item1_id}#cl4",
                    "moveId": move_item1_id,
                    "title": "To do D",
                    "status": "todo",
                }

                checklist_item2_1 = {
                    "checklistId": f"{move_item2_id}#cl1",
                    "moveId": move_item2_id,
                    "title": "To do A",
                    "status": "failed",
                }
                checklist_item2_2 = {
                    "checklistId": f"{move_item2_id}#cl2",
                    "moveId": move_item2_id,
                    "title": "To do B",
                    "status": "todo",
                }
                checklist_item2_3 = {
                    "checklistId": f"{move_item2_id}#cl3",
                    "moveId": move_item2_id,
                    "title": "To do C",
                    "status": "todo",
                }
                checklist_item2_4 = {
                    "checklistId": f"{move_item2_id}#cl4",
                    "moveId": move_item2_id,
                    "title": "To do D",
                    "status": "todo",
                }

                checklist_item3_1 = {
                    "checklistId": f"{move_item3_id}#cl1",
                    "moveId": move_item3_id,
                    "title": "To do A",
                    "status": "todo",
                }
                checklist_item3_2 = {
                    "checklistId": f"{move_item3_id}#cl2",
                    "moveId": move_item3_id,
                    "title": "To do B",
                    "status": "todo",
                }
                try:
                    checklists_table.put_item(Item=checklist_item1_1)
                    checklists_table.put_item(Item=checklist_item1_2)
                    checklists_table.put_item(Item=checklist_item1_3)
                    checklists_table.put_item(Item=checklist_item1_4)
                    checklists_table.put_item(Item=checklist_item2_1)
                    checklists_table.put_item(Item=checklist_item2_2)
                    checklists_table.put_item(Item=checklist_item2_3)
                    checklists_table.put_item(Item=checklist_item2_4)
                    checklists_table.put_item(Item=checklist_item3_1)
                    checklists_table.put_item(Item=checklist_item3_2)
                except Exception as inner_e:
                    print(f"Failed to seed default checklist for {user_sub}: {str(inner_e)}")
        except Exception as seed_e:
            # Swallow any seeding errors to not block signup
            print(f"Post-signup seeding error: {str(seed_e)}")

        return {
            "message": "Signup successful. Check your email for verification code.",
            "user_sub": response.get("UserSub"),
            "confirmation_required": not response.get("UserConfirmed", False)
        }
        
    except cognito_client.exceptions.UsernameExistsException:
        raise HTTPException(status_code=400, detail="User already exists")
    except cognito_client.exceptions.InvalidPasswordException:
        raise HTTPException(status_code=400, detail="Password does not meet requirements")
    except cognito_client.exceptions.InvalidParameterException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

# --- CONFIRM SIGNUP ---
@app.post("/confirm-signup")
def confirm_signup(username: str = Form(...), code: str = Form(...)):
    """Confirm user signup with verification code"""
    try:
        confirm_params = {
            "ClientId": CLIENT_ID,
            "Username": username,  # Use username, not email
            "ConfirmationCode": code
        }
        
        secret_hash = calculate_secret_hash(username)  # Use username for hash
        if secret_hash:
            confirm_params["SecretHash"] = secret_hash
        
        cognito_client.confirm_sign_up(**confirm_params)
        return {"message": "User confirmed successfully. You can now sign in."}
        
    except cognito_client.exceptions.CodeMismatchException:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    except cognito_client.exceptions.ExpiredCodeException:
        raise HTTPException(status_code=400, detail="Verification code has expired")
    except cognito_client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")

# --- RESEND CONFIRMATION CODE ---
@app.post("/resend-confirmation")
def resend_confirmation(username: str = Form(...)):
    """Resend confirmation code"""
    try:
        resend_params = {
            "ClientId": CLIENT_ID,
            "Username": username  # Use username, not email
        }
        
        secret_hash = calculate_secret_hash(username)  # Use username for hash
        if secret_hash:
            resend_params["SecretHash"] = secret_hash
        
        cognito_client.resend_confirmation_code(**resend_params)
        return {"message": "Confirmation code resent successfully"}
        
    except cognito_client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except cognito_client.exceptions.InvalidParameterException:
        raise HTTPException(status_code=400, detail="User is already confirmed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resend code: {str(e)}")

# --- DIRECT SIGNIN ---
@app.post("/signin")
def signin(email: str = Form(...), password: str = Form(...)):
    """Direct sign in with email and password"""
    try:
        auth_params = {
            "USERNAME": email,
            "PASSWORD": password
        }
        
        # Add SECRET_HASH if CLIENT_SECRET is configured
        secret_hash = calculate_secret_hash(email)
        if secret_hash:
            auth_params["SECRET_HASH"] = secret_hash
        
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",  # Make sure this is enabled in Cognito
            AuthParameters=auth_params
        )
        
        if "ChallengeName" in response:
            # Handle challenges (MFA, password reset, etc.)
            return {
                "challenge": response["ChallengeName"],
                "session": response.get("Session"),
                "challenge_parameters": response.get("ChallengeParameters", {})
            }
        
        tokens = response["AuthenticationResult"]
        
        # Decode ID token to get user info
        id_payload = verify_jwt_token(tokens["IdToken"])
        
        # Store/update user in DynamoDB (include phone)
        user_item = {
            "userId": id_payload.get("sub"),
            "email": id_payload.get("email"),
            "name": id_payload.get("name", ""),
            "phone": id_payload.get("phone_number", ""),  # Add phone from JWT
            "email_verified": id_payload.get("email_verified", False)
        }
        users_table.put_item(Item=user_item)
        
        return {
            "message": "Sign in successful",
            "tokens": {
                "access_token": tokens["AccessToken"],
                "id_token": tokens["IdToken"],
                "refresh_token": tokens.get("RefreshToken"),
                "expires_in": tokens.get("ExpiresIn")
            },
            "user": user_item
        }
        
    except cognito_client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except cognito_client.exceptions.UserNotConfirmedException:
        raise HTTPException(status_code=400, detail="User email not confirmed")
    except cognito_client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sign in failed: {str(e)}")

# --- REFRESH TOKEN ---
@app.post("/refresh-token")
def refresh_token(refresh_token: str = Form(...)):
    """Refresh access token using refresh token"""
    try:
        auth_params = {"REFRESH_TOKEN": refresh_token}
        
        # Add SECRET_HASH if CLIENT_SECRET is configured
        if CLIENT_SECRET:
            import hmac
            import hashlib
            # For refresh, we need the username from the refresh token
            # This is a simplified approach - in production, you might want to store this differently
            message = "" + CLIENT_ID  # Empty username for refresh
            secret_hash = base64.b64encode(
                hmac.new(CLIENT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
            ).decode()
            auth_params["SECRET_HASH"] = secret_hash
        
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters=auth_params
        )
        
        tokens = response["AuthenticationResult"]
        
        return {
            "message": "Token refreshed successfully",
            "tokens": {
                "access_token": tokens["AccessToken"],
                "id_token": tokens["IdToken"],
                "expires_in": tokens.get("ExpiresIn")
            }
        }
        
    except cognito_client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")

# --- OAUTH2 LOGIN REDIRECT (for hosted UI) ---
@app.get("/login")
def login():
    """Redirect to Cognito hosted UI for login"""
    if not COGNITO_DOMAIN or not CLIENT_ID:
        raise HTTPException(status_code=500, detail="COGNITO_DOMAIN and CLIENT_ID must be set")
    
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email profile",
        "prompt": "login"
    }
    
    url = f"{COGNITO_DOMAIN}/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(url)

# --- AUTH CALLBACK (for hosted UI) ---
@app.get("/auth/callback")
def auth_callback(code: str = None, error: str = None):
    """Handle OAuth2 callback from Cognito hosted UI"""
    if error:
        raise HTTPException(status_code=400, detail=f"Authentication error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    # Exchange code for tokens
    token_url = f"{COGNITO_DOMAIN}/oauth2/token"
    
    auth_header = None
    if CLIENT_SECRET:
        # Use client credentials for confidential clients
        credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        auth_header = f"Basic {credentials}"
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if auth_header:
        headers["Authorization"] = auth_header
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    
    # Add client_id for public clients
    if not CLIENT_SECRET:
        data["client_id"] = CLIENT_ID
    
    try:
        resp = requests.post(token_url, data=data, headers=headers)
        resp.raise_for_status()
        tokens = resp.json()
        
        # Verify and decode ID token
        id_payload = verify_jwt_token(tokens["id_token"])
        
        # Store/update user in DynamoDB (include phone)
        user_item = {
            "userId": id_payload.get("sub"),
            "email": id_payload.get("email"),
            "name": id_payload.get("name", ""),
            "phone": id_payload.get("phone_number", ""),  # Add phone from JWT
            "email_verified": id_payload.get("email_verified", False)
        }
        users_table.put_item(Item=user_item)
        
        return {
            "message": "Login successful",
            "tokens": tokens,
            "user": user_item
        }
        
    except requests.HTTPError as e:
        error_detail = e.response.text if hasattr(e, 'response') else str(e)
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {error_detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

# --- LOGOUT ---
@app.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (invalidate tokens on Cognito side)"""
    # Note: For complete logout, you'd typically want to revoke the refresh token
    # This requires additional implementation with Cognito
    return {"message": "Logout successful"}

# --- PROTECTED ROUTES ---
@app.get("/me")
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information from JWT token"""
    return {
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "phone": current_user.get("phone_number", ""),  # Add phone
        "email_verified": current_user.get("email_verified", False),
        "token_use": current_user.get("token_use")
    }

# --- GET USER INFO ---
@app.get("/users/{user_id}")
def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get user information by ID (protected route)"""
    try:
        resp = users_table.get_item(Key={"userId": user_id})
        user_data = resp.get("Item", {})
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Only allow users to access their own data or implement admin check
        if current_user.get("sub") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return user_data
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user: {str(e)}")

# --- PASSWORD RESET ---
@app.post("/forgot-password")
def forgot_password(email: str = Form(...)):
    """Initiate password reset process"""
    try:
        forgot_params = {
            "ClientId": CLIENT_ID,
            "Username": email
        }
        
        secret_hash = calculate_secret_hash(email)
        if secret_hash:
            forgot_params["SecretHash"] = secret_hash
        
        cognito_client.forgot_password(**forgot_params)
        return {"message": "Password reset code sent to your email"}
        
    except cognito_client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password reset failed: {str(e)}")

@app.post("/confirm-forgot-password")
def confirm_forgot_password(
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...)
):
    """Confirm password reset with code and new password"""
    try:
        confirm_forgot_params = {
            "ClientId": CLIENT_ID,
            "Username": email,
            "ConfirmationCode": code,
            "Password": new_password
        }
        
        secret_hash = calculate_secret_hash(email)
        if secret_hash:
            confirm_forgot_params["SecretHash"] = secret_hash
        
        cognito_client.confirm_forgot_password(**confirm_forgot_params)
        return {"message": "Password reset successful"}
        
    except cognito_client.exceptions.CodeMismatchException:
        raise HTTPException(status_code=400, detail="Invalid reset code")
    except cognito_client.exceptions.ExpiredCodeException:
        raise HTTPException(status_code=400, detail="Reset code has expired")
    except cognito_client.exceptions.InvalidPasswordException:
        raise HTTPException(status_code=400, detail="Password does not meet requirements")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password reset confirmation failed: {str(e)}")

# --- SSE STREAM FOR AGENTS ---
@app.get("/run-agents-stream")
async def run_agents_stream(current_user: dict = Depends(get_current_user)):
    """
    Stream agent execution progress via Server-Sent Events (SSE)
    """
    async def event_generator():
        try:
            user_id = current_user.get("sub")
            
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Starting agents...'})}\n\n"
            await asyncio.sleep(0.1)
            
            # 1. Fetch user details
            user_details = {
                "name": current_user.get("name", ""),
                "email": current_user.get("email", ""),
                "phone": current_user.get("phone_number", ""),
            }
            
            # 2. Fetch latest move
            try:
                response = moves_table.query(
                    KeyConditionExpression="userId = :uid",
                    ExpressionAttributeValues={":uid": user_id},
                    ScanIndexForward=False,
                    Limit=1
                )
                
                if not response.get("Items"):
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No move found. Please submit move details first.'})}\n\n"
                    return
                    
                move = response["Items"][0]
                user_details.update({
                    "from_address": move.get("fromAddress", ""),
                    "to_address": move.get("toAddress", ""),
                    "moving_date": move.get("moveInDate", ""),
                    "moving_out_date": move.get("moveOutDate", "")
                })
                
            except ClientError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to fetch move details: {str(e)}'})}\n\n"
                return
            
            # Send user details loaded event
            yield f"data: {json.dumps({'type': 'user_details', 'data': user_details})}\n\n"
            await asyncio.sleep(0.5)
            
            # 3. Initialize state
            initial_state = {
                "messages": [],
                "user_id": user_id,
                "user_details": user_details,
                "checklist": [],
                "steps": 0,
                "done": False,
                "next_task": "",
                "reason": ""
            }
            
            # 4. Run orchestrator synchronously (will block, but that's the reality)
            # Note: To make this truly streaming, orchestrator needs to be refactored to yield events
            yield f"data: {json.dumps({'type': 'status', 'message': 'Running agent workflow...'})}\n\n"
            
            # Run in thread pool to avoid blocking event loop completely
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_orchestrator_agent, initial_state)
            
            # 5. Convert checklist to dict format
            checklist_dicts = []
            for item in result.get("checklist", []):
                if isinstance(item, ChecklistItem):
                    checklist_dicts.append({
                        "title": item.title,
                        "status": item.status,
                        "detail": item.detail,
                        "agent_label": item.agent_label,
                        "required_fields": item.required_fields,
                        "depends_on": item.depends_on
                    })
                else:
                    checklist_dicts.append(item)
            
            # Send checklist generated event
            yield f"data: {json.dumps({'type': 'checklist', 'data': checklist_dicts})}\n\n"
            await asyncio.sleep(0.5)

            # 6. Send final completion
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
            "Access-Control-Allow-Origin": "*"
        }
    )
    
# --- HEALTH CHECK ---
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "transitly-backend"}

# --- MOVE ---
@app.post("/move")
def submit_move_details(data: MoveDetails, current_user: dict = Depends(get_current_user)): 
    user_id = current_user.get("sub")

    move_item = {
        "userId" : user_id,
        "moveId" : f"{user_id}#{data.move_out_date}",
        "fromAddress" : data.from_address,
        "toAddress" : data.to_address,
        "moveOutDate" : data.move_out_date.isoformat(),
        "moveInDate" : data.move_in_date.isoformat(),
        "createdAt" : date.today().isoformat()
    }

    try:
        moves_table.put_item(Item=move_item)
        return {
            "message": "Move details saved successfully.",
            "data": move_item
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save move: {str(e)}")
    
# --- RUN AGENTS ---
@app.post("/run-agents")
def run_agents(current_user: dict = Depends(get_current_user)):
    """
    Run the agent orchestrator workflow for the current user's move.
    Fetches user details and move information, then executes the agent workflow.
    """
    try:
        user_id = current_user.get("sub")
        
        # 1. Fetch user info from Cognito token
        user_details = {
            "name": current_user.get("name", ""),
            "email": current_user.get("email", ""),
            "phone": current_user.get("phone_number", ""),
        }
        
        # 2. Fetch latest move details from DynamoDB
        try:
            # Query moves table for this user's most recent move
            response = moves_table.query(
                KeyConditionExpression="userId = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,  # Sort descending by moveId
                Limit=1
            )
            
            if response.get("Items"):
                move = response["Items"][0]
                user_details.update({
                    "from_address": move.get("fromAddress", ""),
                    "to_address": move.get("toAddress", ""),
                    "moving_date": move.get("moveInDate", ""),
                    "moving_out_date": move.get("moveOutDate", "")
                })
            else:
                raise HTTPException(
                    status_code=404, 
                    detail="No move found for user. Please submit move details first."
                )
                
        except ClientError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch move details: {str(e)}"
            )
        
        # 3. Initialize orchestrator state
        initial_state = {
            "messages": [],
            "user_id": user_id,
            "user_details": user_details,
            "checklist": [],
            "steps": 0,
            "done": False,
            "next_task": "",
            "reason": ""
        }
        
        # 4. Run orchestrator
        result = run_orchestrator_agent(initial_state)
        
        # 5. Convert ChecklistItem objects to dicts for JSON serialization
        checklist_dicts = []
        for item in result.get("checklist", []):
            if isinstance(item, ChecklistItem):
                checklist_dicts.append({
                    "title": item.title,
                    "status": item.status,
                    "detail": item.detail,
                    "agent_label": item.agent_label,
                    "required_fields": item.required_fields,
                    "depends_on": item.depends_on
                })
            else:
                checklist_dicts.append(item)

        # 6. Return results
        return {
            "message": "Agent workflow completed",
            "checklist": checklist_dicts,
            "steps": result.get("steps", 0),
            "done": result.get("done", False),
            "user_details": result.get("user_details", {}),
            "address_change_result": result.get("address_change_result", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent workflow failed: {str(e)}"
        )
        
    return {"status": "healthy", "service": "transitly-backend"}

# --- CHECKLISTS ENDPOINT ---
@app.get("/checklists")
def get_checklists(current_user: dict = Depends(get_current_user)):
    """Return aggregated checklists for the authenticated user.

    Flow:
    1) Query TransitlyMoves by userId
    2) For each moveId, query TransitlyChecklists and aggregate items
    """
    try:
        user_id = current_user.get("sub")

        # 1) Get all moves for this user (latest first)
        moves_resp = moves_table.query(
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False
        )

        moves = moves_resp.get("Items", [])
        if not moves:
            return {"checklists": []}

        aggregated = []
        for move in moves:
            move_id = move.get("moveId")
            if not move_id:
                continue

            # 2) Get checklist items for this moveId using scan
            cl_resp = checklists_table.scan(
                FilterExpression="moveId = :mid",
                ExpressionAttributeValues={":mid": move_id}
            )

            items = cl_resp.get("Items", [])
            checklist = [
                {"title": i.get("title", ""), "status": i.get("status", "todo")}
                for i in items
            ]

            aggregated.append({
                "checklistId": move_id,  # use moveId as stable identifier for the card
                "createdAt": move.get("createdAt", datetime.utcnow().isoformat()),
                "fromAddress": move.get("fromAddress", ""),
                "toAddress": move.get("toAddress", ""),
                "moveOutDate": move.get("moveOutDate", ""),
                "moveInDate": move.get("moveInDate", ""),
                "checklist": checklist,
            })

        return {"checklists": aggregated}

    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"DynamoDB error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load checklists: {str(e)}")

# --- DELETE MOVE + ITS CHECKLIST ITEMS BY moveId ---
@app.delete("/move/{move_id}")
def delete_move_and_checklist(move_id: str, current_user: dict = Depends(get_current_user)):
    """
    Delete a move (TransitlyMoves) by moveId for the authenticated user and
    remove all checklist items (TransitlyChecklists) that reference the same moveId.
    """
    user_id = current_user.get("sub")

    # 1 Delete the move item using the composite key (userId, moveId)
    try:
        moves_table.delete_item(
            Key={"userId": user_id, "moveId": move_id},
            ConditionExpression="attribute_exists(moveId)"
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise HTTPException(status_code=404, detail="Move not found")
        raise HTTPException(status_code=500, detail=f"Failed to delete move: {str(e)}")

    # 2 Find and delete all checklist items with this moveId
    try:
        cl_resp = checklists_table.scan(
            FilterExpression="moveId = :mid",
            ExpressionAttributeValues={":mid": move_id}
        )
        items = cl_resp.get("Items", [])

        if items:
            with checklists_table.batch_writer() as batch:
                for item in items:
                    checklist_pk = item.get("checklistId")
                    if checklist_pk:
                        batch.delete_item(Key={"checklistId": checklist_pk})
    except ClientError as e:
        # Move already deleted, but checklist cleanup failed
        raise HTTPException(status_code=500, detail=f"Failed to delete checklist items: {str(e)}")

    return {"message": "Move and associated checklist items deleted successfully.", "moveId": move_id}

# --- CHAT WITH AGENT ---
class ChatMessage(BaseModel):
    message: str
    checklist_context: Optional[List[Dict[str, Any]]] = None

@app.post("/chat")
async def chat_with_agent(
    data: ChatMessage,
    current_user: dict = Depends(get_current_user)
):
    """
    Chat with AI assistant about move tasks.
    Can provide checklist context for task-aware responses.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        
        user_id = current_user.get("sub")
        user_name = current_user.get("name", "").split()[0]
        
        # Get user's move context
        response = moves_table.query(
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,
            Limit=1
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
            checklist_context = "\nCurrent checklist:\n" + "\n".join([
                f"- {item['title']}: {item['status']}" 
                for item in data.checklist_context
            ])
        
        system_prompt = f"""You are a helpful moving assistant for {user_name}.
You help with relocation tasks like updating addresses, transferring utilities, etc.

{move_context}
{checklist_context}

Be concise, helpful, and action-oriented. If the user asks about a task, 
explain what needs to be done and offer to help automate it if possible."""

        llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=data.message)
        ]
        
        response = llm.invoke(messages)
        
        return {
            "message": response.content,
            "timestamp": date.today().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")