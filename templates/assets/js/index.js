document.addEventListener("DOMContentLoaded", () => {
    const internalGrid = document.getElementById("internal-services-grid");
    const internalSection = document.getElementById("internal-services-section");

    if (internalGrid && internalGrid.dataset.loading === "true") {
        // Fetch accessible internal services asynchronously
        fetch("/api/v1/internal_services")
            .then(response => response.json())
            .then(data => {
                internalGrid.dataset.loading = "false";
                internalGrid.innerHTML = "";

                if (data.services && data.services.length > 0) {
                    data.services.forEach(service => {
                        const card = createServiceCard(service);
                        internalGrid.appendChild(card);
                    });
                    // Trigger quota and stat fetches for the newly mounted cards
                    loadServiceStats();
                } else {
                    // If user has no accessible internal services, cleanly hide the section
                    if (internalSection) {
                        internalSection.style.display = "none";
                    }
                }
            })
            .catch(error => {
                console.error("Error fetching internal services:", error);
                internalGrid.dataset.loading = "false";
                internalGrid.innerHTML = "";
                const errorMsg = document.createElement("p");
                errorMsg.classList.add("service-note", "failure");
                errorMsg.textContent = "Failed to load internal services.";
                internalGrid.appendChild(errorMsg);
            });
    } else {
        // Services were already rendered server-side from cache
        loadServiceStats();
    }
});

function createServiceCard(service) {
    const card = document.createElement("a");
    card.href = service.url;
    card.className = "service-card";
    card.target = "_blank";
    card.id = service.id;

    const img = document.createElement("img");
    img.src = `/services/internal/${service.id}.png?v=2`;
    img.alt = service.name;
    img.className = "service-icon";
    img.onerror = function () {
        this.src = "/favicon.png";
    };

    const name = document.createElement("h4");
    name.className = "service-name";
    name.textContent = service.name;

    const desc = document.createElement("p");
    desc.className = "service-desc";
    desc.textContent = service.description || "";

    card.appendChild(img);
    card.appendChild(name);
    card.appendChild(desc);

    return card;
}

function loadServiceStats() {
    // If the user is logged in, fetch their cloud quota and display it
    const cloudLink = document.getElementById("cloud");
    if (cloudLink && !cloudLink.querySelector(".service-note")) {
        fetch("/api/v1/cloud_quota")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    const quotaLabel = document.createElement("p");
                    quotaLabel.classList.add("service-note");
                    quotaLabel.textContent = `${data.used.toLocaleString()} GB used / ${data.total.toLocaleString()} GB total`;
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
    if (immichLink && !immichLink.querySelector(".service-note")) {
        fetch("/api/v1/immich")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    const statsLabel = document.createElement("p");
                    statsLabel.classList.add("service-note");
                    statsLabel.style.whiteSpace = 'pre-wrap';
                    statsLabel.textContent = `Images: ${data.images.toLocaleString()}, Videos: ${data.videos.toLocaleString()}
Storage: ${data.storage}`;
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
    if (linksLink && !linksLink.querySelector(".service-note")) {
        fetch("/api/v1/links")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    const statsLabel = document.createElement("p");
                    statsLabel.classList.add("service-note");
                    statsLabel.textContent = `Links: ${data.links_count.toLocaleString()}`;
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
    if (vpnLink && !vpnLink.querySelector(".service-note")) {
        fetch("https://vpn.woodburn.net.au/api/v1/status")
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    const statusLabel = document.createElement("p");
                    statusLabel.classList.add("service-note");
                    statusLabel.textContent = data.connected ? "Connected" : "Disconnected";
                    if (data.connected) {
                        statusLabel.classList.add("success");
                    } else {
                        statusLabel.classList.add("failure");
                    }
                    vpnLink.appendChild(statusLabel);
                } else {
                    console.error("Error fetching VPN status:", data.error);
                }
            })
            .catch(error => {
                console.error("Error fetching VPN status:", error);
            });
    }
}
