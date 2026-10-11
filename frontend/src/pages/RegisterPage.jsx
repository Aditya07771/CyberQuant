import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Shield, UserPlus, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { getApiErrorMessage } from '../api/client';

export function RegisterPage() {
  const navigate = useNavigate();
  const { signUp, busy } = useAuth();
  const [form, setForm] = useState({
    fullName: '',
    email: '',
    password: '',
    organizationName: '',
  });
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    try {
      await signUp({
        email: form.email,
        password: form.password,
        fullName: form.fullName,
        organizationName: form.organizationName,
      });
      navigate('/', { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Unable to create your account. Please review the form and try again.'));
    }
  };

  const fieldClass =
    'w-full px-3 py-2 text-sm bg-th-surface border border-th-border rounded-lg text-th-text-primary placeholder-th-text-muted focus:outline-none focus:ring-2 focus:ring-th-brand focus:border-transparent';

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-th-bg theme-transition">
      <Card className="w-full max-w-md" elevated>
        <CardHeader>
          <div className="w-full flex flex-col items-center text-center gap-2">
            <div className="w-11 h-11 rounded-xl bg-th-brand flex items-center justify-center text-white">
              <Shield className="w-6 h-6" />
            </div>
            <CardTitle className="text-2xl">Create your organization</CardTitle>
            <CardDescription>
              You will be provisioned as the organization owner
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
              <label htmlFor="fullName" className="text-xs font-medium text-th-text-secondary">
                Full name
              </label>
              <input
                id="fullName"
                name="fullName"
                type="text"
                required
                autoComplete="name"
                value={form.fullName}
                onChange={handleChange}
                className={fieldClass}
                placeholder="Ada Lovelace"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="organizationName" className="text-xs font-medium text-th-text-secondary">
                Organization name
              </label>
              <input
                id="organizationName"
                name="organizationName"
                type="text"
                required
                value={form.organizationName}
                onChange={handleChange}
                className={fieldClass}
                placeholder="Acme Financial"
              />
            </div>

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
                className={fieldClass}
                placeholder="analyst@company.com"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-xs font-medium text-th-text-secondary">
                Password <span className="text-th-text-muted">(min. 8 characters)</span>
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={form.password}
                onChange={handleChange}
                className={fieldClass}
                placeholder="••••••••"
              />
            </div>

            <Button type="submit" size="lg" isLoading={busy} className="w-full gap-2">
              {!busy && <UserPlus className="w-4 h-4" />}
              Create account
            </Button>
          </form>

          <p className="text-xs text-center text-th-text-secondary">
            Already have an account?{' '}
            <Link to="/login" className="text-th-brand font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default RegisterPage;
