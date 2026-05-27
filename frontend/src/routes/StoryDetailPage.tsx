import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AxisCoverageBar, BucketPill, PortalAxisPills } from '../components/BlindspotBar';
import { OrientationBadge } from '../components/OrientationBadge';
import { ApiError, getStory } from '../lib/api';
import type { AxisBucket, AxisCoverage, AxisId, StoryArticle, StoryDetail } from '../types';

const AXIS_LABEL: Record<AxisId, string> = {
  statism_liberalism: 'Estatismo / liberalismo',
  peronism_antiperonism: 'Peronismo / antiperonismo',
};

const AXIS_BUCKETS: Record<AxisId, AxisBucket[]> = {
  statism_liberalism: ['estatista', 'centro', 'liberal'],
  peronism_antiperonism: ['peronista', 'centro', 'antiperonista'],
};

const BUCKET_LABEL: Record<string, string> = {
  estatista: 'estatismo',
  liberal: 'liberalismo',
  peronista: 'peronismo',
  antiperonista: 'antiperonismo',
  centro: 'centro',
};

function bucketForAxis(article: StoryArticle, axis: AxisId): AxisBucket {
  if (axis === 'statism_liberalism') return article.economic_bucket;
  return article.peronism_bucket;
}

function axisBlindspotText(axisCoverage: AxisCoverage[]): string {
  const parts = axisCoverage
    .filter((axis) => axis.blindspots.length > 0)
    .map(
      (axis) =>
        `${AXIS_LABEL[axis.axis]}: ${axis.blindspots
          .map((bucket) => BUCKET_LABEL[bucket] ?? String(bucket))
          .join(', ')}`,
    );
  return parts.join(' · ');
}

function ArticleCard({ article }: { article: StoryArticle }) {
  return (
    <article className="flex flex-col gap-2 rounded-xl border border-ink/10 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink/60">
        <span className="font-semibold text-ink">{article.portal_name}</span>
        <PortalAxisPills
          economicBucket={article.economic_bucket}
          peronismBucket={article.peronism_bucket}
        />
      </div>
      <Link
        to={`/articulos/${article.article_id}`}
        className="font-serif text-base font-semibold leading-snug hover:text-accent"
      >
        {article.title || '(sin titular)'}
      </Link>
      <div className="flex flex-wrap gap-1.5">
        {article.statism_liberalism_score !== null && (
          <OrientationBadge
            score={article.statism_liberalism_score}
            size="sm"
            axis="statism_liberalism"
          />
        )}
        {article.peronism_antiperonism_score !== null && (
          <OrientationBadge
            score={article.peronism_antiperonism_score}
            size="sm"
            axis="peronism_antiperonism"
          />
        )}
      </div>
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-accent hover:underline"
      >
        original →
      </a>
      {article.overall_label && <p className="text-sm text-ink/70">{article.overall_label}</p>}
      {article.published_at && (
        <p className="text-xs text-ink/50">
          {new Date(article.published_at).toLocaleString('es-AR')}
        </p>
      )}
    </article>
  );
}

export function StoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<StoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getStory(Number(id))
      .then(setData)
      .catch((err) =>
        setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error'),
      );
  }, [id]);

  if (error) {
    return (
      <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
        {error}
      </div>
    );
  }

  if (!data) return <p className="text-ink/60">Cargando…</p>;

  const hasAxisBlindspot = data.axis_coverage.some((axis) => axis.blindspots.length > 0);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-3 border-b border-ink/10 pb-6">
        <h1 className="font-serif text-3xl font-bold leading-snug sm:text-4xl">
          {data.canonical_title}
        </h1>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink/60">
          <span>{data.article_count} artículos</span>
          <span>
            {new Date(data.first_seen_at).toLocaleString('es-AR')} →{' '}
            {new Date(data.last_seen_at).toLocaleString('es-AR')}
          </span>
        </div>
      </header>

      {hasAxisBlindspot && (
        <section className="rounded-2xl border-l-4 border-amber-400 bg-amber-50 p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-amber-700">
            Blindspot detectado
          </div>
          <p className="mt-1 text-base text-amber-900">
            Falta cobertura en <strong>{axisBlindspotText(data.axis_coverage)}</strong> entre los
            portales que monitoreamos.
          </p>
        </section>
      )}

      <section className="grid gap-4 lg:grid-cols-2">
        {data.axis_coverage.map((axis) => (
          <div key={axis.axis} className="flex flex-col gap-4 rounded-2xl border border-ink/10 bg-white p-6">
            <AxisCoverageBar axisCoverage={axis} />
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        {data.axis_coverage.map((axis) => (
          <div key={axis.axis} className="flex flex-col gap-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-ink/50">
              Agrupado por {AXIS_LABEL[axis.axis].toLowerCase()}
            </h2>
            {AXIS_BUCKETS[axis.axis].map((bucket) => {
              const arts = data.articles.filter((article) => bucketForAxis(article, axis.axis) === bucket);
              const isBlindspot = axis.blindspots.includes(bucket);
              return (
                <div key={bucket} className="flex flex-col gap-3">
                  <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold uppercase tracking-wider text-ink/50">
                    <BucketPill bucket={bucket} axis={axis.axis} />
                    {isBlindspot && (
                      <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-900">
                        sin cobertura
                      </span>
                    )}
                  </h3>
                  {arts.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50/50 px-4 py-6 text-center text-sm text-amber-900">
                      Ningún portal de este bucket cubrió esta historia.
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {arts.map((article) => (
                        <ArticleCard key={`${axis.axis}-${bucket}-${article.article_id}`} article={article} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </section>
    </div>
  );
}
