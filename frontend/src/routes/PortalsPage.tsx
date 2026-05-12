import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listPortals, refreshAllPortals, ApiError } from '../lib/api';
import { OrientationBadge } from '../components/OrientationBadge';
import { PortalAxisPills } from '../components/BlindspotBar';
import type { PortalSummary } from '../types';

function formatRelative(iso: string | null): string {
  if (!iso) return 'sin refrescar todavía';
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return 'hace segundos';
  if (mins < 60) return `hace ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs} h`;
  return `hace ${Math.floor(hrs / 24)} d`;
}

export function PortalsPage() {
  const [portals, setPortals] = useState<PortalSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      setError(null);
      setPortals(await listPortals());
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error desconocido');
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleRefreshAll = async () => {
    setRefreshing(true);
    try {
      await refreshAllPortals();
      setTimeout(() => void load(), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error refrescando');
    } finally {
      setTimeout(() => setRefreshing(false), 2000);
    }
  };

  const totalAnalyzed = portals?.reduce((sum, p) => sum + p.aggregate.analyzed_count, 0) ?? 0;

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-3">
        <h1 className="font-serif text-3xl font-bold leading-tight sm:text-4xl">
          Los principales medios argentinos
        </h1>
        <p className="max-w-2xl text-ink/70">
          Cada 30 minutos Sesgómetro descubre los últimos artículos de cada portada y los ubica en
          dos ejes argentinos: estatismo/liberalismo y peronismo/antiperonismo.
        </p>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ink/10 bg-white px-4 py-3">
        <div className="text-sm text-ink/70">
          {portals ? (
            <>
              <strong className="text-ink">{portals.length}</strong> medios ·{' '}
              <strong className="text-ink">{totalAnalyzed}</strong> artículos analizados
            </>
          ) : (
            'Cargando…'
          )}
        </div>
        <button
          onClick={handleRefreshAll}
          disabled={refreshing}
          className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-paper transition hover:bg-ink/90 disabled:opacity-50"
        >
          {refreshing ? 'Refrescando…' : 'Refrescar todos'}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>
      )}

      {portals && (
        <ul className="grid gap-4 sm:grid-cols-2">
          {portals.map((portal) => (
            <li key={portal.slug}>
              <Link
                to={`/portales/${portal.slug}`}
                className="group flex h-full flex-col gap-3 rounded-2xl border border-ink/10 bg-white p-5 transition hover:border-accent hover:shadow"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-serif text-xl font-bold leading-tight">{portal.name}</h2>
                    </div>
                    {portal.description && (
                      <p className="mt-1 text-sm text-ink/60">{portal.description}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <OrientationBadge
                      score={portal.aggregate.avg_statism_liberalism}
                      size="sm"
                      axis="statism_liberalism"
                    />
                    <OrientationBadge
                      score={portal.aggregate.avg_peronism_antiperonism}
                      size="sm"
                      axis="peronism_antiperonism"
                    />
                  </div>
                </div>

                <PortalAxisPills
                  economicBucket={portal.economic_bucket}
                  peronismBucket={portal.peronism_bucket}
                />

                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink/60">
                  <span>{portal.aggregate.analyzed_count} analizados</span>
                  {portal.aggregate.avg_emotional_load !== null && (
                    <span>
                      carga emocional media{' '}
                      <strong className="text-ink">
                        {(portal.aggregate.avg_emotional_load * 100).toFixed(0)}%
                      </strong>
                    </span>
                  )}
                  <span>actualizado {formatRelative(portal.last_refreshed_at)}</span>
                </div>

                <span className="mt-auto text-sm font-medium text-accent group-hover:underline">
                  Ver artículos →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
