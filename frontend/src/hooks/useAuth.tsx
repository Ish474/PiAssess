import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearAuth, getCachedUser, setAuth } from "../api/client";
import type { User } from "../api/types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>({ user: null, loading: true, login: async () => {}, logout: async () => {} });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(getCachedUser<User>());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.post<{ user: User; csrf_token: string }>("/api/auth/login", { username, password });
    setAuth(res.csrf_token, res.user);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      clearAuth();
      setUser(null);
    }
  }, []);

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  return useContext(Ctx);
}
