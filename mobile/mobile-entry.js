const API_ORIGIN_KEY = "touchline:mobile-api-origin";
const root = document.querySelector("#app");
const params = new URLSearchParams(window.location.search);

window.TOUCHLINE_MOBILE = true;

function cleanOrigin(value) {
  const url = new URL(value.trim());
  if (!(["http:", "https:"].includes(url.protocol)) || url.username || url.password || url.search || url.hash || (url.pathname !== "/" && url.pathname !== "")) {
    throw new Error("Enter only the server address, such as https://club.example.com.");
  }
  if (url.protocol === "http:") {
    const host = url.hostname.toLowerCase();
    const isLoopback = ["localhost", "127.0.0.1", "::1"].includes(host);
    const isPrivateIPv4 = /^10\./.test(host) || /^192\.168\./.test(host) || /^172\.(1[6-9]|2\d|3[01])\./.test(host);
    const isLocalName = host.endsWith(".local") || host.endsWith(".lan");
    if (!(isLoopback || isPrivateIPv4 || isLocalName)) throw new Error("Use HTTPS for internet servers. HTTP is allowed only for a local network test server.");
  }
  return url.origin;
}

function launch(origin) {
  window.TOUCHLINE_API_BASE = `${origin}/api/v1`;
  import("./js/app.js");
}

function renderSetup(message = "") {
  const saved = localStorage.getItem(API_ORIGIN_KEY) || "";
  root.innerHTML = `<main class="mobile-connect">
    <div class="mobile-connect__brand"><span>TL</span><p>TOUCHLINE <small>CLUBHOUSE</small></p></div>
    <p class="mobile-connect__eyebrow">Connect your clubhouse</p>
    <h1>One squad.<br>Every screen.</h1>
    <p class="mobile-connect__intro">Connect to the same Touchline server used by the web app. Your account, communities and activity stay in sync.</p>
    <form id="mobile-connect-form">
      <label for="mobile-api-origin">Server address</label>
      <input id="mobile-api-origin" name="origin" type="url" inputmode="url" autocomplete="url" placeholder="https://your-clubhouse.example.com" value="${saved.replaceAll("&", "&amp;").replaceAll('"', "&quot;")}" required>
      <small>For testing on home Wi-Fi, enter your computer's local address and port, such as http://192.168.1.20:4173.</small>
      <p id="mobile-connect-error" role="alert" ${message ? "" : "hidden"}>${message}</p>
      <button type="submit">Connect to server</button>
    </form>
    <footer>All sign-ins and club data use the same secure API as the web app.</footer>
  </main>`;
  root.querySelector("#mobile-connect-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.currentTarget.querySelector("button");
    const error = root.querySelector("#mobile-connect-error");
    button.disabled = true;
    button.textContent = "Checking server…";
    error.hidden = true;
    try {
      const origin = cleanOrigin(new FormData(event.currentTarget).get("origin"));
      const response = await fetch(`${origin}/api/v1/health`, { headers: { Accept: "application/json" } });
      const result = await response.json();
      if (!response.ok || result?.data?.status !== "ok") throw new Error("The server responded, but its Touchline API is not healthy.");
      localStorage.setItem(API_ORIGIN_KEY, origin);
      history.replaceState({}, "", `${location.pathname}${location.hash}`);
      launch(origin);
    } catch (cause) {
      error.textContent = cause instanceof TypeError
        ? "Could not reach that server. If its health URL opens in your phone's browser, install the latest Android debug build and try again. Release builds require an HTTPS server."
        : cause.message;
      error.hidden = false;
      button.disabled = false;
      button.textContent = "Connect to server";
    }
  });
}

const configuredOrigin = localStorage.getItem(API_ORIGIN_KEY);
if (configuredOrigin && !params.has("mobileConfigure")) {
  try {
    launch(cleanOrigin(configuredOrigin));
  } catch {
    localStorage.removeItem(API_ORIGIN_KEY);
    renderSetup("The saved server address is invalid. Enter it again.");
  }
} else {
  renderSetup();
}
