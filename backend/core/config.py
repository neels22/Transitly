import os
from dotenv import load_dotenv
import boto3

# Load environment variables
load_dotenv()

# === Environment / Settings ===
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN")
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:8000/auth/callback")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
DDB_TABLE = os.environ.get("DDB_TABLE", "TransitlyUsers")
DDB_MOVES_TABLE = os.environ.get("DDB_MOVES_TABLE", "TransitlyMoves")
DDB_CHECKLISTS_TABLE = os.environ.get("DDB_CHECKLISTS_TABLE", "TransitlyChecklists")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
USER_POOL_ID = os.environ.get("USER_POOL_ID")

# === AWS SDK Clients ===
boto_kwargs = {"region_name": AWS_REGION}
if DYNAMODB_ENDPOINT:
    boto_kwargs["endpoint_url"] = DYNAMODB_ENDPOINT

dynamodb = boto3.resource("dynamodb", **boto_kwargs)
users_table = dynamodb.Table(DDB_TABLE)
moves_table = dynamodb.Table(DDB_MOVES_TABLE)
checklists_table = dynamodb.Table(DDB_CHECKLISTS_TABLE)

cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)


