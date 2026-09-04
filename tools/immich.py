import os

import requests

IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")


def bytes_to_human_readable(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"


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
    storage_used = 0
    for user in data:
        if user.get("oauthId") == user_sub:
            user_id = user.get("id")
            storage_used = user.get("quotaUsageInBytes")
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
    stats["storage"] = bytes_to_human_readable(storage_used)
    return stats
