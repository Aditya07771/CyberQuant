import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import {
  readAuth,
  writeAuth,
  clearAuth,
  login as apiLogin,
  demoLogin as apiDemoLogin,
  register as apiRegister,
  logout as apiLogout,
} from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => readAuth());
  const [busy, setBusy] = useState(false);

  const persist = useCallback((next) => {
    if (next) {
      writeAuth(next);
    } else {
      clearAuth();
    }
    setAuth(next);
  }, []);

  const signIn = useCallback(
    async (credentials) => {
      setBusy(true);
      try {
        const res = await apiLogin(credentials);
        const next = {
          user: res.user,
          organization: res.organization,
          tokens: res.tokens,
        };
        persist(next);
        return next;
      } finally {
        setBusy(false);
      }
    },
    [persist],
  );

  const signInDemo = useCallback(
    async (payload) => {
      setBusy(true);
      try {
        const res = await apiDemoLogin(payload);
        const next = {
          user: res.user,
          organization: res.organization,
          tokens: res.tokens,
        };
        persist(next);
        return next;
      } finally {
        setBusy(false);
      }
    },
    [persist],
  );

  const signUp = useCallback(
    async (payload) => {
      setBusy(true);
      try {
        const res = await apiRegister(payload);
        const next = {
          user: res.user,
          organization: res.organization,
          tokens: res.tokens,
        };
        persist(next);
        return next;
      } finally {
        setBusy(false);
      }
    },
    [persist],
  );

  const signOut = useCallback(async () => {
    await apiLogout();
    persist(null);
  }, [persist]);

  // Clear local session when the API layer reports an unrecoverable 401.
  useEffect(() => {
    const onUnauthorized = () => persist(null);
    window.addEventListener('cyberquant:unauthorized', onUnauthorized);
    return () => window.removeEventListener('cyberquant:unauthorized', onUnauthorized);
  }, [persist]);

  const isAuthenticated = Boolean(auth?.tokens?.access_token);

  const value = {
    auth,
    user: auth?.user || null,
    organization: auth?.organization || null,
    isAuthenticated,
    busy,
    signIn,
    signInDemo,
    signUp,
    signOut,
    updateProfile: persist,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
