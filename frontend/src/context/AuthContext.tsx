import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  ApiError,
  fetchMe,
  getStoredToken,
  login as apiLogin,
  setStoredToken,
  signup as apiSignup,
} from '../lib/api';
import type { User } from '../types';

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          setStoredToken(null);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    setStoredToken(res.access_token);
    setUser(res.user);
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const res = await apiSignup(email, password);
    setStoredToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    setStoredToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, signup, logout }),
    [user, loading, login, signup, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (ctx === null) throw new Error('useAuth fuera de AuthProvider');
  return ctx;
}
