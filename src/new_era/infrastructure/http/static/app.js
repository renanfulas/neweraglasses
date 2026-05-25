async function loadHealth() {
  const apiStatus = document.getElementById("api-status");
  const deviceStatus = document.getElementById("device-status");
  const versionStatus = document.getElementById("version-status");

  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error(`health returned ${response.status}`);
    }
    const payload = await response.json();
    apiStatus.textContent = payload.status || "ok";
    deviceStatus.textContent = payload.device_gateway || "unknown";
    versionStatus.textContent = payload.version || "0.1.0";
  } catch (error) {
    apiStatus.textContent = "unavailable";
    deviceStatus.textContent = "unavailable";
    versionStatus.textContent = "unavailable";
    console.error("Failed to load health status", error);
  }
}

document.getElementById("refresh-health")?.addEventListener("click", () => {
  loadHealth();
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch((error) => {
      console.warn("Service worker registration failed", error);
    });
  });
}

loadHealth();
