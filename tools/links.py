import os
import requests

LINKS_API_KEY = os.getenv("LINKS_API_KEY")


def get_links_stats(user_email: str) -> dict[str, int | str]:
    """
    Get the user's Immich stats from the API.
    """
    if not LINKS_API_KEY:
        return {"error": "LINKS_API_KEY environment variable not set"}
    headers = {"x-api-key": LINKS_API_KEY, "Accept": "application/json"}
    response = requests.get("https://l.woodburn.au/api/v2/users/admin", headers=headers)
    if response.status_code != 200:
        return {"error": f"Failed to fetch Links stats: {response.status_code}"}
    data = response.json()
    if not data.get("data"):
        return {"error": "User not found in Links"}
    for user in data["data"]:
        if user.get("email") == user_email:
            return user
    return {"error": "User not found in Links"}
