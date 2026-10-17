import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Shield, LogIn, AlertCircle, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { getApiErrorMessage, listDemoAccounts } from '../api/client';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn, signInDemo, busy } = useAuth();
  const [form, setForm] = useState({ email: '', password: '', organizationId: '' });
  const [error, setError] = useState(null);
  const [demoAccounts, setDemoAccounts] = useState([]);
  const [demoBusyKey, setDemoBusyKey] = useState(null);

  const redirectTo = location.state?.from?.pathname || '/';

  useEffect(() => {
    let active = true;
    listDemoAccounts()
      .then((accounts) => {
        if (active) setDemoAccounts(accounts);
      })
      .catch(() => {
        /* demo login unavailable; ignore */
      });
    return () => {
      active = false;
    };
  }, []);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await signIn({
        email: form.email,
        password: form.password,
        organizationId: form.organizationId || undefined,
      });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Unable to sign in. Check your credentials and try again.'));
    }
  };

  const handleDemoLogin = async (account) => {
    setError(null);
    setDemoBusyKey(account.key);
    try {
      await signInDemo({ key: account.key });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Unable to start the demo session.'));
    } finally {
      setDemoBusyKey(null);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-th-bg theme-transition">
      <Card className="w-full max-w-md" elevated>
        <CardHeader>
          <div className="w-full flex flex-col items-center text-center gap-2">
            <div className="w-11 h-11 rounded-xl bg-th-brand items-center justify-center text-white flex">
              <Shield className="w-6 h-6" />
            </div>
            <CardTitle className="text-2xl">Sign in to CyberQuant</CardTitle>
            <CardDescription>
              FAIR-aligned enterprise cyber risk quantification
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-th-danger-tint border border-th-danger/30 text-th-danger text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {demoAccounts.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-medium text-th-text-secondary">
                <Zap className="w-3.5 h-3.5 text-th-brand" />
                One-click demo login
              </div>
              <div className="grid gap-2">
                {demoAccounts.map((account) => (
                  <button
                    key={account.key}
                    type="button"
                    onClick={() => handleDemoLogin(account)}
                    disabled={busy || demoBusyKey !== null}
                    className="w-full text-left px-3 py-2.5 rounded-lg border border-th-border bg-th-surface hover:bg-th-surface-el hover:border-th-brand transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-th-text-primary">
                        {account.label}
                      </span>
                      {demoBusyKey === account.key ? (
                        <span className="text-xs text-th-text-muted">Signing in…</span>
                      ) : (
                        <LogIn className="w-4 h-4 text-th-text-muted" />
                      )}
                    </div>
                    {account.blurb && (
                      <p className="text-[11px] text-th-text-muted mt-0.5">{account.blurb}</p>
                    )}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-th-border" />
                <span className="text-[11px] uppercase tracking-wide text-th-text-muted">or</span>
                <div className="h-px flex-1 bg-th-border" />
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-xs font-medium text-th-text-secondary">
                Work email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="email"
                value={form.email}
                onChange={handleChange}
                className="w-full px-3 py-2 text-sm bg-th-surface border border-th-border rounded-lg text-th-text-primary placeholder-th-text-muted focus:outline-none focus:ring-2 focus:ring-th-brand focus:border-transparent"
                placeholder="analyst@company.com"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-xs font-medium text-th-text-secondary">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                autoComplete="current-password"
                value={form.password}
                onChange={handleChange}
                className="w-full px-3 py-2 text-sm bg-th-surface border border-th-border rounded-lg text-th-text-primary placeholder-th-text-muted focus:outline-none focus:ring-2 focus:ring-th-brand focus:border-transparent"
                placeholder="••••••••"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="organizationId" className="text-xs font-medium text-th-text-secondary">
                Organization ID <span className="text-th-text-muted">(only if you belong to multiple)</span>
              </label>
              <input
                id="organizationId"
                name="organizationId"
                type="text"
                value={form.organizationId}
                onChange={handleChange}
                className="w-full px-3 py-2 text-sm bg-th-surface border border-th-border rounded-lg text-th-text-primary placeholder-th-text-muted focus:outline-none focus:ring-2 focus:ring-th-brand focus:border-transparent font-mono"
                placeholder="optional"
              />
            </div>

            <Button type="submit" size="lg" isLoading={busy} className="w-full gap-2">
              {!busy && <LogIn className="w-4 h-4" />}
              Sign in
            </Button>
          </form>

          <p className="text-xs text-center text-th-text-secondary">
            Need an account?{' '}
            <Link to="/register" className="text-th-brand font-medium hover:underline">
              Create an organization
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default LoginPage;
