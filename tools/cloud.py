import os
import requests

login = os.getenv("WOODBURN_USER")


def getUserQuota(user: str) -> dict[str, int | str]:
    """
    Get the user's quota information from the environment variable.
    Returns a dictionary with 'used' and 'total' as integers.
    """
    headers = {"OCS-APIRequest": "true", "Accept": "application/json"}
    if not login:
        return {
            "used": 0,
            "total": 5,
            "percentage": "0.0",
            "error": "WOODBURN_USER environment variable not set",
        }
    # curl -u user https://cloud.woodburn.au/ocs/v1.php/cloud/users/nathan OCS-APIRequest:true
    response = requests.get(
        f"https://cloud.woodburn.au/ocs/v1.php/cloud/users/{user}",
        headers=headers,
        auth=(login.split(":")[0], login.split(":")[1]),
    )
    if response.status_code != 200:
        return {
            "used": 0,
            "total": 5,
            "percentage": "0.0",
            "error": f"Failed to fetch quota: {response.status_code}",
        }
    data = response.json()
    # If the request failed
    if data.get("ocs", {}).get("meta", {}).get("status") != "ok":
        return {
            "used": 0,
            "total": 5,
            "percentage": "0.0",
            "error": data.get("ocs", {})
            .get("meta", {})
            .get("message", "Unknown error"),
        }

    quota = data.get("ocs", {}).get("data", {}).get("quota", {})
    # Convert to GB
    used = int(quota.get("used", 0)) // (1024 * 1024 * 1024)
    total = int(quota.get("total", 0)) // (1024 * 1024 * 1024)
    return {"used": used, "total": total, "percentage": quota.get("relative", "0.0")}
