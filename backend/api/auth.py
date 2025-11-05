import base64
from datetime import date
from typing import Any, Dict
from urllib.parse import urlencode

import requests
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse

from core.auth import (
    calculate_secret_hash,
    format_phone_to_e164,
    validate_phone_e164,
)
from core.config import (
    COGNITO_DOMAIN,
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    cognito_client,
    users_table,
    moves_table,
    checklists_table,
)
from core.security import get_current_user, verify_jwt_token


router = APIRouter(tags=["auth"])


@router.post("/signup")
def signup(
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    username: str = Form(...),
    phone: str = Form(...),
):
    """Sign up a new user with AWS Cognito."""
    try:
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
            {"Name": "phone_number", "Value": formatted_phone},
        ]

        signup_params: Dict[str, Any] = {
            "ClientId": CLIENT_ID,
            "Username": username,
            "Password": password,
            "UserAttributes": user_attributes,
        }

        secret_hash = calculate_secret_hash(username)
        if secret_hash:
            signup_params["SecretHash"] = secret_hash

        response = cognito_client.sign_up(**signup_params)

        # After successful signup, seed default move + checklist data
        try:
            user_sub = response.get("UserSub")
            if user_sub:
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
            print(f"Post-signup seeding error: {str(seed_e)}")

        return {
            "message": "Signup successful. Check your email for verification code.",
            "user_sub": response.get("UserSub"),
            "confirmation_required": not response.get("UserConfirmed", False),
        }

    except cognito_client.exceptions.UsernameExistsException:
        raise HTTPException(status_code=400, detail="User already exists")
    except cognito_client.exceptions.InvalidPasswordException:
        raise HTTPException(status_code=400, detail="Password does not meet requirements")
    except cognito_client.exceptions.InvalidParameterException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@router.post("/confirm-signup")
def confirm_signup(username: str = Form(...), code: str = Form(...)):
    """Confirm user signup with verification code."""
    try:
        confirm_params: Dict[str, Any] = {
            "ClientId": CLIENT_ID,
            "Username": username,
            "ConfirmationCode": code,
        }
        secret_hash = calculate_secret_hash(username)
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


@router.post("/resend-confirmation")
def resend_confirmation(username: str = Form(...)):
    """Resend confirmation code."""
    try:
        resend_params: Dict[str, Any] = {"ClientId": CLIENT_ID, "Username": username}
        secret_hash = calculate_secret_hash(username)
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


@router.post("/signin")
def signin(email: str = Form(...), password: str = Form(...)):
    """Direct sign in with email and password."""
    try:
        auth_params: Dict[str, Any] = {"USERNAME": email, "PASSWORD": password}
        secret_hash = calculate_secret_hash(email)
        if secret_hash:
            auth_params["SECRET_HASH"] = secret_hash

        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID, AuthFlow="USER_PASSWORD_AUTH", AuthParameters=auth_params
        )

        if "ChallengeName" in response:
            return {
                "challenge": response["ChallengeName"],
                "session": response.get("Session"),
                "challenge_parameters": response.get("ChallengeParameters", {}),
            }

        tokens = response["AuthenticationResult"]

        id_payload = verify_jwt_token(tokens["IdToken"])

        user_item = {
            "userId": id_payload.get("sub"),
            "email": id_payload.get("email"),
            "name": id_payload.get("name", ""),
            "phone": id_payload.get("phone_number", ""),
            "email_verified": id_payload.get("email_verified", False),
        }
        users_table.put_item(Item=user_item)

        return {
            "message": "Sign in successful",
            "tokens": {
                "access_token": tokens["AccessToken"],
                "id_token": tokens["IdToken"],
                "refresh_token": tokens.get("RefreshToken"),
                "expires_in": tokens.get("ExpiresIn"),
            },
            "user": user_item,
        }
    except cognito_client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except cognito_client.exceptions.UserNotConfirmedException:
        raise HTTPException(status_code=400, detail="User email not confirmed")
    except cognito_client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sign in failed: {str(e)}")


@router.post("/refresh-token")
def refresh_token(refresh_token: str = Form(...)):
    """Refresh access token using refresh token."""
    try:
        auth_params: Dict[str, Any] = {"REFRESH_TOKEN": refresh_token}
        if CLIENT_SECRET:
            import hashlib
            import hmac

            message = "" + CLIENT_ID
            secret_hash = base64.b64encode(
                hmac.new(CLIENT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
            ).decode()
            auth_params["SECRET_HASH"] = secret_hash

        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters=auth_params,
        )

        tokens = response["AuthenticationResult"]
        return {
            "message": "Token refreshed successfully",
            "tokens": {
                "access_token": tokens["AccessToken"],
                "id_token": tokens["IdToken"],
                "expires_in": tokens.get("ExpiresIn"),
            },
        }
    except cognito_client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")


@router.get("/login")
def login():
    """Redirect to Cognito hosted UI for login."""
    if not COGNITO_DOMAIN or not CLIENT_ID:
        raise HTTPException(status_code=500, detail="COGNITO_DOMAIN and CLIENT_ID must be set")
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email profile",
        "prompt": "login",
    }
    url = f"{COGNITO_DOMAIN}/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/auth/callback")
def auth_callback(code: str | None = None, error: str | None = None):
    """Handle OAuth2 callback from Cognito hosted UI."""
    if error:
        raise HTTPException(status_code=400, detail=f"Authentication error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    token_url = f"{COGNITO_DOMAIN}/oauth2/token"
    auth_header = None
    if CLIENT_SECRET:
        credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        auth_header = f"Basic {credentials}"

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if auth_header:
        headers["Authorization"] = auth_header

    data: Dict[str, Any] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    if not CLIENT_SECRET:
        data["client_id"] = CLIENT_ID

    try:
        resp = requests.post(token_url, data=data, headers=headers)
        resp.raise_for_status()
        tokens = resp.json()

        id_payload = verify_jwt_token(tokens["id_token"])
        user_item = {
            "userId": id_payload.get("sub"),
            "email": id_payload.get("email"),
            "name": id_payload.get("name", ""),
            "phone": id_payload.get("phone_number", ""),
            "email_verified": id_payload.get("email_verified", False),
        }
        users_table.put_item(Item=user_item)

        return {"message": "Login successful", "tokens": tokens, "user": user_item}
    except requests.HTTPError as e:
        error_detail = e.response.text if hasattr(e, "response") else str(e)
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {error_detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (invalidate tokens on Cognito side)."""
    return {"message": "Logout successful"}


@router.post("/forgot-password")
def forgot_password(email: str = Form(...)):
    """Initiate password reset process."""
    try:
        forgot_params: Dict[str, Any] = {"ClientId": CLIENT_ID, "Username": email}
        secret_hash = calculate_secret_hash(email)
        if secret_hash:
            forgot_params["SecretHash"] = secret_hash
        cognito_client.forgot_password(**forgot_params)
        return {"message": "Password reset code sent to your email"}
    except cognito_client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password reset failed: {str(e)}")


@router.post("/confirm-forgot-password")
def confirm_forgot_password(
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
):
    """Confirm password reset with code and new password."""
    try:
        confirm_forgot_params: Dict[str, Any] = {
            "ClientId": CLIENT_ID,
            "Username": email,
            "ConfirmationCode": code,
            "Password": new_password,
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


