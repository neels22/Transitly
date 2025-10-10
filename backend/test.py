# test.py
# Test the exact same flow as your FastAPI code
import os
import boto3
import hmac, hashlib, base64

CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
CLIENT_ID = os.environ.get('CLIENT_ID')
AWS_REGION = os.environ.get('AWS_REGION')

def calculate_secret_hash(username: str):
    if not CLIENT_SECRET:
        return None
    message = username + CLIENT_ID
    return base64.b64encode(
        hmac.new(CLIENT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()

# Simulate your FastAPI signup function exactly
email = 'test101@example.com'
password = 'Password123!'
name = 'TestUser'

user_attributes = [{'Name': 'email', 'Value': email}]
if name:
    user_attributes.append({'Name': 'name', 'Value': name})

signup_params = {
    'ClientId': CLIENT_ID,
    'Username': email,
    'Password': password,
    'UserAttributes': user_attributes
}

secret_hash = calculate_secret_hash(email)
print('Secret hash calculated:', secret_hash is not None)
if secret_hash:
    signup_params['SecretHash'] = secret_hash

print('Final params keys:', list(signup_params.keys()))
print('SecretHash in params:', 'SecretHash' in signup_params)

# Test the call
cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)
try:
    response = cognito_client.sign_up(**signup_params)
    print('SUCCESS: Signup worked via direct simulation')
except Exception as e:
    print('ERROR in simulation:', str(e))
