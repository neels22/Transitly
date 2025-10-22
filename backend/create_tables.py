import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# For running from HOST machine (not inside Docker)
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv('AWS_REGION', 'us-east-2'),
    endpoint_url='http://localhost:8001',  # Host machine connects to Docker on 8001
    aws_access_key_id='fakeAccessKeyId',
    aws_secret_access_key='fakeSecretAccessKey'
)

def create_tables():
    print("🔧 Creating DynamoDB tables...")
    
    # Create transitlyUsers table
    try:
        dynamodb.create_table(
            TableName='transitlyUsers',
            KeySchema=[
                {'AttributeName': 'userId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'userId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("✅ Created transitlyUsers table")
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print("ℹ️  transitlyUsers table already exists")
    except Exception as e:
        print(f"❌ Error creating transitlyUsers: {e}")

    # Create transitlyMoves table
    try:
        dynamodb.create_table(
            TableName='transitlyMoves',
            KeySchema=[
                {'AttributeName': 'userId', 'KeyType': 'HASH'},
                {'AttributeName': 'moveId', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'userId', 'AttributeType': 'S'},
                {'AttributeName': 'moveId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("✅ Created transitlyMoves table")
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print("ℹ️  transitlyMoves table already exists")
    except Exception as e:
        print(f"❌ Error creating transitlyMoves: {e}")

if __name__ == "__main__":
    create_tables()
    print("\n🎉 Database setup complete!")