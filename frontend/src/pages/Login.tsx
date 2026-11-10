import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Button, Input, Label } from "../components/ui";

export default function Login() {
  const { user, loading, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <img src="/api/settings/logo" alt="Pi World School" className="mx-auto h-20 w-auto max-w-[280px] rounded-lg bg-white object-contain px-2 py-1.5" />
          <h1 className="mt-3 text-lg font-semibold text-ink">Pi World School</h1>
          <p className="text-xs text-stone-500">Forbesganj, Bihar · PiAssess Academic Evaluation Suite</p>
        </div>
        <form onSubmit={onSubmit} className="rounded-xl border border-stone-200 bg-white p-6 shadow-card">
          <div className="space-y-3">
            <div>
              <Label htmlFor="username">Username</Label>
              <Input id="username" autoFocus autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
            <Button type="submit" className="w-full" loading={busy}>
              Sign in
            </Button>
          </div>
        </form>
        <p className="mt-4 text-center text-[11px] text-stone-400">
          Academic Session 2026–27 · Authorised staff only
        </p>
      </div>
    </div>
  );
}
