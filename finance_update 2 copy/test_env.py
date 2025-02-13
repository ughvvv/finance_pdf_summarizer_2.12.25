import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

required_vars = [
    'OPENAI_API_KEY',
    'DROPBOX_REFRESH_TOKEN',
    'DROPBOX_APP_KEY',
    'DROPBOX_APP_SECRET',
    'EMAIL_USERNAME',
    'EMAIL_PASSWORD'
]

print("Environment variables status:")
for var in required_vars:
    value = os.getenv(var)
    if value:
        print(f"{var}: ✓ (Set)")
    else:
        print(f"{var}: ✗ (Not set)")
