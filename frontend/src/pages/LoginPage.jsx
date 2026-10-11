import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Shield, LogIn, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { getApiErrorMessage } from '../api/client';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn, busy } = useAuth();
  const [form, setForm] = useState({ email: '', password: '', organizationId: '' });
  const [error, setError] = useState(null);

  const redirectTo = location.state?.from?.pathname || '/';

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

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-th-bg theme-transition">
      <Card className="w-full max-w-md" elevated>
        <CardHeader>
          <div className="w-full flex flex-col items-center text-center gap-2">
            <div className="w-11 h-11 rounded-xl bg-th-brand flex items-center justify-center text-white">
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
