import { createContext, useContext, useState } from "react";

const API_URL = "http://localhost:8000";
const AuthContext = createContext(null);

function parseToken(t) {
  try {
    const payload = JSON.parse(atob(t.split(".")[1]));
    return { id: parseInt(payload.sub), role: payload.role };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("access_token"));
  const [user, setUser] = useState(() => {
    const t = localStorage.getItem("access_token");
    return t ? parseToken(t) : null;
  });

  function setAuth(accessToken) {
    localStorage.setItem("access_token", accessToken);
    setToken(accessToken);
    setUser(parseToken(accessToken));
  }

  function clearAuth() {
    localStorage.removeItem("access_token");
    setToken(null);
    setUser(null);
  }

  async function login(email, password) {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const { access_token } = await res.json();
    setAuth(access_token);
  }

  async function register(name, email, password) {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ name, email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed");
    }
    const { access_token } = await res.json();
    setAuth(access_token);
  }

  async function logout() {
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" }).catch(() => {});
    clearAuth();
  }

  async function refreshAccessToken(currentToken) {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) { clearAuth(); return null; }
    const { access_token } = await res.json();
    setAuth(access_token);
    return access_token;
  }

  /**
   * Authenticated fetch wrapper.
   * - Attaches Bearer token automatically.
   * - On 401, attempts a token refresh once then retries.
   * - On second 401, clears auth (session expired).
   */
  async function apiFetch(url, options = {}) {
    const makeHeaders = (t) => ({
      "Content-Type": "application/json",
      ...(options.headers || {}),
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
    });

    let res = await fetch(url, { ...options, headers: makeHeaders(token), credentials: "include" });

    if (res.status === 401) {
      const newToken = await refreshAccessToken(token);
      if (newToken) {
        res = await fetch(url, { ...options, headers: makeHeaders(newToken), credentials: "include" });
      } else {
        return res; // clearAuth already called
      }
    }

    return res;
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, register, apiFetch }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
