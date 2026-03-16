import os
import requests

IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")


def get_immich_stats(user_sub: str) -> dict[str, int | str]:
    """
    Get the user's Immich stats from the API.
    """
    if not IMMICH_API_KEY:
        return {"error": "IMMICH_API_KEY environment variable not set"}
    headers = {"x-api-key": IMMICH_API_KEY, "Accept": "application/json"}
    response = requests.get(
        "https://immich.woodburn.au/api/admin/users", headers=headers
    )
    if response.status_code != 200:
        return {"error": f"Failed to fetch Immich stats: {response.status_code}"}
    data = response.json()
    user_id = None
    for user in data:
        if user.get("oauthId") == user_sub:
            user_id = user.get("id")
            break
    if not user_id:
        return {"error": "User not found in Immich"}
    # Get user stats
    response = requests.get(
        f"https://immich.woodburn.au/api/admin/users/{user_id}/statistics",
        headers=headers,
    )
    if response.status_code != 200:
        return {"error": f"Failed to fetch Immich user stats: {response.status_code}"}
    stats = response.json()
    return stats
