import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AnalysisResult } from '../components/AnalysisResult';
import { PortalAxisPills } from '../components/BlindspotBar';
import { FavoriteButton } from '../components/FavoriteButton';
import { ApiError, getArticle } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import type { ArticleDetail } from '../types';

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [data, setData] = useState<ArticleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setData(null);
    setError(null);
    getArticle(Number(id))
      .then(setData)
      .catch((err) =>
        setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error'),
      );
  }, [id]);

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

  if (!data) return <p className="text-ink/60">Cargando…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to={`/portales/${data.portal.slug}`} className="text-sm text-accent hover:underline">
          ← Volver a {data.portal.name}
        </Link>
        {data.story_id !== null && (
          <Link
            to={`/historias/${data.story_id}`}
            className="text-sm text-accent hover:underline"
          >
            Ver historia agrupada →
          </Link>
        )}
      </div>

      <section className="flex flex-wrap items-center gap-3 rounded-xl border border-ink/10 bg-white px-4 py-3">
        <span className="font-semibold">{data.portal.name}</span>
        <PortalAxisPills
          economicBucket={data.portal.economic_bucket}
          peronismBucket={data.portal.peronism_bucket}
        />
        {user && <FavoriteButton articleId={Number(id)} initial={data.is_favorite} />}
        <a
          href={data.article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto text-sm text-accent hover:underline"
        >
          original ↗
        </a>
      </section>

      {data.analysis ? (
        <AnalysisResult data={{ article: data.article, analysis: data.analysis }} />
      ) : (
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-6 text-center text-sm text-amber-900">
          Este artículo todavía no fue analizado. Esperá al próximo refresh o pulsá <strong>Refrescar
          ahora</strong> desde la página del portal.
        </div>
      )}
    </div>
  );
}
