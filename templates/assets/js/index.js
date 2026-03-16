document.addEventListener("DOMContentLoaded", () => {
    // If the user is logged in, fetch their cloud quota and display it
    const cloudLink = document.getElementById("cloud");
    if (cloudLink) {
        fetch("/api/v1/cloud_quota")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    // Create a new span element to display the quota
                    const quotaLabel = document.createElement("p");
                    quotaLabel.classList.add("service-note");
                    quotaLabel.textContent = `${data.used} GB used / ${data.total} GB total`;
                    // Append the quota span to the cloud link
                    cloudLink.appendChild(quotaLabel);
                } else {
                    console.error("Error fetching cloud quota:", data.error);
                }
            })
            .catch(error => {
                console.error("Error fetching cloud quota:", error);
            });
    }

    // Fetch Immich stats and display them
    const immichLink = document.getElementById("immich");
    if (immichLink) {
        fetch("/api/v1/immich")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    // Create a new span element to display the stats
                    const statsLabel = document.createElement("p");
                    statsLabel.classList.add("service-note");
                    statsLabel.textContent = `Images: ${data.images}, Videos: ${data.videos}`;
                    // Append the stats span to the Immich link
                    immichLink.appendChild(statsLabel);
                } else {
                    console.error("Error fetching Immich stats:", data.error);
                }
            })
            .catch(error => {
                console.error("Error fetching Immich stats:", error);
            });
    }
});