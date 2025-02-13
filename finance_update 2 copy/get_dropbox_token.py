"""Script to obtain a Dropbox refresh token."""

import os
from dropbox import DropboxOAuth2FlowNoRedirect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get app key and secret from environment
APP_KEY = os.getenv('DROPBOX_APP_KEY')
APP_SECRET = os.getenv('DROPBOX_APP_SECRET')

def get_refresh_token():
    """Get a refresh token using the OAuth2 flow."""
    auth_flow = DropboxOAuth2FlowNoRedirect(
        APP_KEY,
        APP_SECRET,
        token_access_type='offline'
    )

    # Get the authorization URL
    authorize_url = auth_flow.start()
    print("1. Go to this URL:", authorize_url)
    print("2. Click 'Allow' (you might have to log in first).")
    print("3. Copy the authorization code.")

    # Get the authorization code from user input
    auth_code = input("Enter the authorization code here: ").strip()

    try:
        # This will get both an access token and refresh token
        oauth_result = auth_flow.finish(auth_code)
        print("\nSuccess! Here's your refresh token:")
        print(oauth_result.refresh_token)
        print("\nUpdate your .env file with this token as DROPBOX_REFRESH_TOKEN")
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    if not APP_KEY or not APP_SECRET:
        print("Error: Make sure DROPBOX_APP_KEY and DROPBOX_APP_SECRET are set in your .env file")
    else:
        get_refresh_token()
