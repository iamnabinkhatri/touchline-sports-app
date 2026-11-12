const TOKEN_KEY = "touchline:session";
const API_BASE = globalThis.window?.TOUCHLINE_API_BASE || "/api/v1";

let token = readToken();

export class ApiError extends Error {
  constructor(message, { status = 0, code = "request_failed", fields = {} } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || null;
  } catch {
    return null;
  }
}

export function getSessionToken() {
  return token;
}

export function setSessionToken(value) {
  token = value || null;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // The in-memory session still works when storage is unavailable.
  }
}

export function clearSessionToken() {
  setSessionToken(null);
}

async function request(method, path, body = undefined, options = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError("Cannot reach the Touchline server. Check that it is running.", {
      status: 0,
      code: "network_error",
    });
  }

  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  }

  if (!response.ok || payload?.ok === false) {
    if (response.status === 401 && options.clearOnUnauthorized !== false) {
      clearSessionToken();
    }
    const error = payload?.error ?? {};
    throw new ApiError(error.message || `Request failed (${response.status}).`, {
      status: response.status,
      code: error.code || "request_failed",
      fields: error.fields || {},
    });
  }

  return payload?.data ?? null;
}

export const api = {
  get: (path, options) => request("GET", path, undefined, options),
  post: (path, body, options) => request("POST", path, body ?? {}, options),
  patch: (path, body, options) => request("PATCH", path, body ?? {}, options),
  delete: (path, options) => request("DELETE", path, undefined, options),
};

export async function login(email, password) {
  const data = await request("POST", "/auth/login", { email, password }, { clearOnUnauthorized: false });
  if (data.token) setSessionToken(data.token);
  return data;
}

export async function adminLogin(email, password) {
  const data = await request("POST", "/auth/admin", { email, password }, { clearOnUnauthorized: false });
  if (data.token) setSessionToken(data.token);
  return data;
}

export async function register(name, email, password, playerInvite = null) {
  const data = await request("POST", "/auth/register", { name, email, password, ...(playerInvite ? { player_invite: playerInvite } : {}) }, { clearOnUnauthorized: false });
  if (data.token) setSessionToken(data.token);
  return data;
}

export async function logout() {
  try {
    await request("POST", "/auth/logout");
  } finally {
    clearSessionToken();
  }
}

export async function fetchBootstrap() {
  return request("GET", "/bootstrap");
}

export async function startSession() {
  if (token) {
    return fetchBootstrap();
  }
  throw new ApiError("Sign in to continue.", { status: 401, code: "sign_in_required" });
}
