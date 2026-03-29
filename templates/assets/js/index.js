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
                    statsLabel.textContent = `Images: ${data.images.toLocaleString()}, Videos: ${data.videos}`;
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

    // Fetch Links stats and display them
    const linksLink = document.getElementById("links");
    if (linksLink) {
        fetch("/api/v1/links")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    // Create a new span element to display the stats
                    const statsLabel = document.createElement("p");
                    statsLabel.classList.add("service-note");
                    statsLabel.textContent = `Links: ${data.links_count}`;
                    // Append the stats span to the Links link
                    linksLink.appendChild(statsLabel);
                } else {
                    console.error("Error fetching Links stats:", data.error);
                }
            })
            .catch(error => {
                console.error("Error fetching Links stats:", error);
            });
    }

    // Check VPN status and display it
    const vpnLink = document.getElementById("vpn");
    if (vpnLink) {
        fetch("https://vpn.woodburn.net.au/api/v1/status")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    // Create a new span element to display the VPN status
                    const statusLabel = document.createElement("p");
                    statusLabel.classList.add("service-note");
                    statusLabel.textContent = data.connected ? "Connected" : "Disconnected";
                    if (data.connected) {
                        statusLabel.classList.add("success");
                    } else {
                        statusLabel.classList.add("failure");
                    }
                    // Append the status span to the VPN link
                    vpnLink.appendChild(statusLabel);
                } else {
                    console.error("Error fetching VPN status:", data.error);
                }
            })
            .catch(error => {
                console.error("Error fetching VPN status:", error);
            });
    }
});
