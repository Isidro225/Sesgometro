import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ApiError, listAlerts, markAlertRead, markAllAlertsRead } from '../lib/api';
import type { AlertItem, AxisBucket, AxisCoverage, AxisId } from '../types';

const AXIS_LABEL: Record<AxisId, string> = {
  statism_liberalism: 'estatismo/liberalismo',
  peronism_antiperonism: 'peronismo/antiperonismo',
};

const BUCKET_LABEL: Record<string, string> = {
  estatista: 'estatismo',
  liberal: 'liberalismo',
  peronista: 'peronismo',
  antiperonista: 'antiperonismo',
  centro: 'centro',
  izq: 'izquierda',
  der: 'derecha',
};

function bucketLabel(bucket: AxisBucket): string {
  return BUCKET_LABEL[bucket] ?? String(bucket);
}

function describeBlindspot(axisBlindspots: AxisCoverage[]): string {
  const parts = axisBlindspots
    .filter((axis) => axis.blindspots.length > 0)
    .map(
      (axis) =>
        `${AXIS_LABEL[axis.axis]}: ${axis.blindspots.map((bucket) => bucketLabel(bucket)).join(', ')}`,
    );
  return parts.length > 0 ? `Falta cobertura en ${parts.join(' · ')}.` : '';
}

function formatWhen(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'recién';
  if (mins < 60) return `hace ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs} h`;
  const days = Math.floor(hrs / 24);
  return `hace ${days} d`;
}

export function AlertsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<AlertItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setError(null);
      const r = await listAlerts();
      setItems(r.items);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error');
    }
  };

  useEffect(() => {
    if (user) void load();
  }, [user]);

  const onClickAlert = async (alert: AlertItem) => {
    if (!alert.read) {
      try {
        await markAlertRead(alert.id);
      } catch {
        /* ignore */
      }
    }
  };

  const onReadAll = async () => {
    setBusy(true);
    try {
      await markAllAlertsRead();
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (!user) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Necesitás{' '}
        <Link to="/login" className="font-medium underline">
          entrar
        </Link>{' '}
        para ver tus alertas.
      </div>
    );
  }

  const unread = items?.filter((i) => !i.read).length ?? 0;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="font-serif text-3xl font-bold leading-tight">Alertas de blindspot</h1>
        <p className="text-ink/70">
          Te avisamos cuando una historia con ≥3 artículos no fue cubierta por algún bucket de
          estatismo/liberalismo o peronismo/antiperonismo. Solo se dispara una vez por historia.
        </p>
      </header>

      <div className="flex items-center justify-between rounded-xl border border-ink/10 bg-white px-4 py-3 text-sm">
        <span className="text-ink/70">
          {items === null
            ? 'Cargando…'
            : `${items.length} alertas · ${unread} sin leer`}
        </span>
        {unread > 0 && (
          <button
            onClick={onReadAll}
            disabled={busy}
            className="rounded-lg border border-ink/15 px-3 py-1.5 text-sm text-ink/70 transition hover:border-ink hover:text-ink disabled:opacity-50"
          >
            Marcar todas como leídas
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>
      )}

      {items && items.length === 0 && (
        <div className="rounded-xl border border-ink/10 bg-white px-4 py-8 text-center text-sm text-ink/60">
          Sin alertas todavía. Cuando una historia importante quede sin cubrir por algún bucket argentino, aparecerá acá.
        </div>
      )}

      {items && items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {items.map((alert) => (
            <li key={alert.id}>
              <Link
                to={alert.story_id !== null ? `/historias/${alert.story_id}` : '#'}
                onClick={() => void onClickAlert(alert)}
                className={`flex flex-col gap-2 rounded-xl border p-5 transition ${
                  alert.read
                    ? 'border-ink/10 bg-white hover:border-ink/30'
                    : 'border-amber-300 bg-amber-50/60 hover:border-amber-500'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider">
                    <span className="rounded-full bg-amber-200 px-2 py-0.5 text-amber-900">
                      Blindspot
                    </span>
                    {!alert.read && (
                      <span className="rounded-full bg-accent px-2 py-0.5 text-white">Nueva</span>
                    )}
                  </div>
                  <span className="text-xs text-ink/50">{formatWhen(alert.created_at)}</span>
                </div>
                <h2 className="font-serif text-lg font-bold leading-snug">
                  {alert.story_title || '(sin título)'}
                </h2>
                <p className="text-sm text-ink/70">
                  {alert.article_count} artículo{alert.article_count === 1 ? '' : 's'} ·{' '}
                  {describeBlindspot(alert.axis_blindspots)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
