import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, getPortal, refreshPortal } from '../lib/api';
import { AxisBar } from '../components/AxisBar';
import { OrientationBadge } from '../components/OrientationBadge';
import { PortalAxisPills } from '../components/BlindspotBar';
import { FavoriteButton } from '../components/FavoriteButton';
import type { PortalDetail } from '../types';

export function PortalDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [data, setData] = useState<PortalDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    if (!slug) return;
    try {
      setError(null);
      setData(await getPortal(slug));
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error desconocido');
    }
  };

  useEffect(() => {
    void load();
  }, [slug]);

  const handleRefresh = async () => {
    if (!slug) return;
    setRefreshing(true);
    try {
      await refreshPortal(slug);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error refrescando');
    } finally {
      setRefreshing(false);
    }
  };

  if (!data && !error) {
    return <p className="text-ink/60">Cargando…</p>;
  }

  if (error) {
    return (
      <div className="flex flex-col gap-4">
        <Link to="/portales" className="text-sm text-accent hover:underline">
          ← Volver a portales
        </Link>
        <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>
      </div>
    );
  }

  if (!data) return null;

  const { aggregate } = data;

  return (
    <div className="flex flex-col gap-10">
      <div>
        <Link to="/portales" className="text-sm text-accent hover:underline">
          ← Volver a portales
        </Link>
      </div>

      <header className="flex flex-col gap-3 border-b border-ink/10 pb-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-serif text-3xl font-bold sm:text-4xl">{data.name}</h1>
            </div>
            <div className="mt-2">
              <PortalAxisPills
                economicBucket={data.economic_bucket}
                peronismBucket={data.peronism_bucket}
              />
            </div>
            {data.description && <p className="mt-1 text-ink/60">{data.description}</p>}
            <a
              href={data.homepage_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block text-sm text-accent hover:underline"
            >
              {data.homepage_url} ↗
            </a>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-paper transition hover:bg-ink/90 disabled:opacity-50"
          >
            {refreshing ? 'Refrescando…' : 'Refrescar ahora'}
          </button>
        </div>
      </header>

      {aggregate.analyzed_count === 0 ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Aún no hay artículos analizados para este portal. El job de refresco se ejecuta cada 30 min
          o pulsa <strong>Refrescar ahora</strong> arriba.
        </div>
      ) : (
        <section className="grid gap-6 rounded-2xl border border-ink/10 bg-white p-6 lg:grid-cols-3">
          <div className="flex flex-col gap-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-ink/50">
              Estatismo / liberalismo · {aggregate.analyzed_count} artículos
            </div>
            <AxisBar
              score={aggregate.avg_statism_liberalism ?? 0}
              leftLabel="Estatismo"
              rightLabel="Liberalismo"
              tone="economic"
            />
            <OrientationBadge
              score={aggregate.avg_statism_liberalism}
              size="md"
              axis="statism_liberalism"
            />
          </div>
          <div className="flex flex-col gap-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-ink/50">
              Peronismo / antiperonismo
            </div>
            <AxisBar
              score={aggregate.avg_peronism_antiperonism ?? 0}
              leftLabel="Peronismo"
              rightLabel="Antiperonismo"
              tone="peronism"
            />
            <OrientationBadge
              score={aggregate.avg_peronism_antiperonism}
              size="md"
              axis="peronism_antiperonism"
            />
          </div>
          <div className="flex flex-col gap-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-ink/50">Carga emocional media</div>
            <div className="font-serif text-3xl font-bold">
              {((aggregate.avg_emotional_load ?? 0) * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-ink/60">0 = informativo · 100 = editorial cargado</div>
          </div>
        </section>
      )}

      <section className="flex flex-col gap-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-ink/50">
          Artículos descubiertos ({data.articles.length})
        </h2>
        {data.articles.length === 0 ? (
          <p className="text-ink/60">Sin artículos descubiertos todavía.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {data.articles.map((article) => (
              <li
                key={article.id}
                className="flex flex-col gap-2 rounded-xl border border-ink/10 bg-white p-5 transition hover:border-ink/30"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <Link
                    to={`/articulos/${article.id}`}
                    className="font-serif text-lg font-semibold leading-snug hover:text-accent"
                  >
                    {article.title || '(Artículo sin titular)'}
                  </Link>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <FavoriteButton articleId={article.id} initial={article.is_favorite} />
                    {article.analysis && (
                      <>
                        <OrientationBadge
                          score={article.analysis.statism_liberalism.score}
                          size="sm"
                          axis="statism_liberalism"
                        />
                        <OrientationBadge
                          score={article.analysis.peronism_antiperonism.score}
                          size="sm"
                          axis="peronism_antiperonism"
                        />
                      </>
                    )}
                  </div>
                </div>
                {article.analysis && (
                  <p className="text-sm leading-relaxed text-ink/70">
                    <strong className="text-ink">{article.analysis.overall_label}</strong> ·{' '}
                    {article.analysis.neutral_summary.slice(0, 200)}
                    {article.analysis.neutral_summary.length > 200 && '…'}
                  </p>
                )}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink/50">
                  {article.author && <span>{article.author}</span>}
                  {article.word_count && <span>{article.word_count} palabras</span>}
                  {article.analysis?.is_mock && (
                    <span className="text-amber-700">mock</span>
                  )}
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:underline"
                  >
                    original ↗
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs text-ink/40">
        Refrescado por última vez:{' '}
        {data.last_refreshed_at
          ? new Date(data.last_refreshed_at).toLocaleString('es-ES')
          : 'nunca'}
      </p>
    </div>
  );
}
