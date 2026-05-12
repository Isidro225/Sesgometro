import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../lib/api';

export function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    const fromState = (location.state as { from?: string } | null)?.from;
    navigate(fromState ?? '/', { replace: true });
    return null;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="font-serif text-3xl font-bold leading-tight">Entrar a Sesgómetro</h1>
        <p className="text-ink/70">Tu historial y favoritos quedan guardados en tu cuenta.</p>
      </header>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-2xl border border-ink/10 bg-white p-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-ink/15 px-3 py-2 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
            disabled={submitting}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Contraseña</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-lg border border-ink/15 px-3 py-2 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
            disabled={submitting}
          />
        </label>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">{error}</div>
        )}

        <button
          type="submit"
          disabled={submitting || !email || !password}
          className="rounded-lg bg-ink px-4 py-2.5 font-semibold text-paper transition hover:bg-ink/90 disabled:opacity-50"
        >
          {submitting ? 'Entrando…' : 'Entrar'}
        </button>
      </form>

      <p className="text-sm text-ink/60">
        ¿No tenés cuenta?{' '}
        <Link to="/signup" className="font-medium text-accent hover:underline">
          Creá una en 30 segundos
        </Link>
        .
      </p>
    </div>
  );
}
