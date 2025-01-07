import os
import constants
from instagrapi import Client
from instagrapi.mixins.challenge import ChallengeChoice
from instagrapi.exceptions import ChallengeRequired
from dotenv import load_dotenv

def post_to_instagram(image_path, caption, local_env):
    if local_env:
        load_dotenv()
    username = os.getenv("INSTAGRAM_USERNAME")
    password =os.getenv("INSTAGRAM_PASSWORD")

    cl = login_with_challenge_handling(username, password)
    cl.photo_upload(image_path, caption)


def get_post_text(date):
    return f"""Les dates Bidul du {date} (liste non exhaustive)"""


def login_with_challenge_handling(username, password):
    print(f"Username login: {username}")
    client = Client()
    try:
        client.login(username, password)
        print("Login successful!")
        return client
    except ChallengeRequired as e:
        print("Challenge required. Resolving...")
        resolve_challenge(client)
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def resolve_challenge(client):
    # Get challenge URL
    challenge_url = client.last_json.get("challenge", {}).get("url", "")
    if not challenge_url:
        print("No challenge URL found.")
        return

    # Send verification code via email or SMS (0 for SMS, 1 for email)
    verification_method = 1  # Email (change to 0 for SMS)
    client.challenge_code_send(challenge_url, verification_method)
    print("Verification code sent. Please check your email or SMS.")

    # Simulate fetching the verification code from an external source
    code = fetch_verification_code()  # Replace with your logic
    if not code:
        print("Failed to fetch the verification code.")
        return

    # Submit the verification code
    try:
        client.challenge_code_verify(code)
        print("Challenge resolved successfully!")
    except Exception as e:
        print(f"Failed to resolve challenge: {e}")


def fetch_verification_code():
    """
    Replace this with logic to fetch the verification code
    from an email or SMS API.
    """
    print("Waiting for verification code...")
    time.sleep(30)  # Wait for the code to arrive
    return os.getenv("INSTAGRAM_VERIFICATION_CODE")  # Fetch code from env variable