import { useState } from "react";
import { useAuth } from "./AuthContext";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function switchMode(next) {
    setMode(next);
    setError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (mode === "register") {
      if (name.trim().length < 2) { setError("Name must be at least 2 characters."); return; }
      if (password.length < 8)    { setError("Password must be at least 8 characters."); return; }
    }

    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(name.trim(), email, password);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand">
          <span className="login-brand-dot" aria-hidden="true" />
          <h1 className="login-title">Support desk</h1>
        </div>

        <p className="login-subtitle">
          {mode === "login" ? "Sign in to your account" : "Create a customer account"}
        </p>

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          {mode === "register" && (
            <label className="login-field">
              <span>Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your full name"
                autoComplete="name"
                required
                disabled={loading}
              />
            </label>
          )}

          <label className="login-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
              disabled={loading}
            />
          </label>

          <label className="login-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "Min. 8 characters" : "Your password"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              disabled={loading}
            />
          </label>

          {error && <p className="login-error" role="alert">{error}</p>}

          <button className="login-submit" type="submit" disabled={loading}>
            {loading
              ? "Please wait…"
              : mode === "login"
              ? "Sign in"
              : "Create account"}
          </button>
        </form>

        <p className="login-toggle">
          {mode === "login" ? (
            <>
              Don&apos;t have an account?{" "}
              <button type="button" onClick={() => switchMode("register")}>
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={() => switchMode("login")}>
                Sign in
              </button>
            </>
          )}
        </p>

        {mode === "login" && (
          <p className="login-hint">
            Agents: use the invite link sent to your email to set your password,
            then sign in here.
          </p>
        )}
      </div>
    </div>
  );
}
