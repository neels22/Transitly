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
from datetime import date
from pydantic import BaseModel

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
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
USER_POOL_ID = os.environ.get("USER_POOL_ID")  # Add this to .env

# === Setup DynamoDB ===
boto_kwargs = {"region_name": AWS_REGION}
if DYNAMODB_ENDPOINT:
    boto_kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
dynamodb = boto3.resource("dynamodb", **boto_kwargs)
users_table = dynamodb.Table(DDB_TABLE)
moves_table = dynamodb.Table(DDB_MOVES_TABLE)

# === Setup Cognito client ===
cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)

# === Security ===
security = HTTPBearer()

# JWKS cache
_jwks_cache: Optional[Dict] = None

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
def signup(email: str = Form(...), password: str = Form(...), first_name: str = Form(...), last_name: str = Form(...), username: str = Form(...)):
    """Sign up a new user with AWS Cognito"""
    try:
        user_attributes = [
            {"Name": "email", "Value": email},
            {"Name": "given_name", "Value": first_name},
            {"Name": "family_name", "Value": last_name},
            {"Name": "name", "Value": f"{first_name} {last_name}"}  # This is the formatted name
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
        
        # Store/update user in DynamoDB
        user_item = {
            "userId": id_payload.get("sub"),
            "email": id_payload.get("email"),
            "name": id_payload.get("name", ""),
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
        
        # Store/update user in DynamoDB
        user_item = {
            "userId": id_payload.get("sub"),
            "email": id_payload.get("email"),
            "name": id_payload.get("name", ""),
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
    return {"status": "healthy", "service": "transitly-backend"}

# --- DUMMY CHECKLISTS ENDPOINT ---
@app.get("/checklists")
def get_checklists():
    """Return dummy checklists for now (to be replaced with DynamoDB query later)"""
    dummy_checklists = [
        {
            "checklistId": "cl1",
            "createdAt": "2025-10-20",
            "fromAddress": "1234 Lane lane, Drive drive, San Jose, CA 987653",
            "toAddress": "5678 Driveway driveway, San Mateo, CA 987654",
            "moveOutDate": "2025-12-12",
            "moveInDate": "2025-12-12",
            "checklist": [
                {"title": "To do A", "status": "agentdone"},
                {"title": "To do B", "status": "manualdone"},
                {"title": "To do C", "status": "failed"},
                {"title": "To do D", "status": "todo"},
            ],
        },
        {
            "checklistId": "cl2",
            "createdAt": "2025-10-20",
            "fromAddress": "1234 Lane lane, Drive drive, San Jose, CA 987653",
            "toAddress": "5678 Driveway driveway, San Mateo, CA 987654",
            "moveOutDate": "2025-12-12",
            "moveInDate": "2025-12-12",
            "checklist": [
                {"title": "To do A", "status": "failed"},
                {"title": "To do B", "status": "todo"},
                {"title": "To do C", "status": "todo"},
                {"title": "To do D", "status": "todo"},
            ],
        },
        {
            "checklistId": "cl3",
            "createdAt": "2025-10-20",
            "fromAddress": "1234 Lane lane, Drive drive, San Jose, CA 987653",
            "toAddress": "5678 Driveway driveway, San Mateo, CA 987654",
            "moveOutDate": "2025-12-12",
            "moveInDate": "2025-12-12",
            "checklist": [
                {"title": "To do A", "status": "todo"},
                {"title": "To do B", "status": "todo"}
            ],
        },
    ]
    return {"checklists": dummy_checklists}

# --- DELETE CHECKLIST ---
@app.delete("/checklist/{checklist_id}")
def delete_checklist(checklist_id: str, current_user: dict = Depends(get_current_user)):
    """
    Temporarily simulate checklist deletion.
    Later, integrate with DynamoDB to actually remove by ID.
    """
    # Here you’d call DynamoDB to delete item
    print(f"Deleting checklist {checklist_id} for user {current_user.get('sub')}")
    return {"message": f"Checklist {checklist_id} deleted successfully."}
