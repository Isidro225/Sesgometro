import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AxisCoverageBar } from '../components/BlindspotBar';
import { FeedArticleCard } from '../components/FeedArticleCard';
import { ApiError, listArticles, listPortals, listStories } from '../lib/api';
import type {
  ArticleFeedItem,
  EconomicBucket,
  PeronismBucket,
  PortalSummary,
  StorySummary,
} from '../types';

const PORTAL_COLORS = [
  'bg-rose-500',
  'bg-orange-500',
  'bg-amber-500',
  'bg-emerald-500',
  'bg-teal-500',
  'bg-cyan-500',
  'bg-indigo-500',
  'bg-fuchsia-500',
  'bg-lime-600',
  'bg-stone-600',
] as const;

const CATEGORIES: { name: string; slug: string; tone: string }[] = [
  { name: 'Política', slug: 'politica', tone: 'from-red-500 to-slate-900' },
  { name: 'Economía', slug: 'economia', tone: 'from-emerald-600 to-slate-900' },
  { name: 'Seguridad', slug: 'seguridad', tone: 'from-sky-700 to-zinc-900' },
  { name: 'Internacional', slug: 'internacional', tone: 'from-indigo-600 to-stone-900' },
  { name: 'Salud', slug: 'salud', tone: 'from-rose-500 to-slate-950' },
  { name: 'Ambiente', slug: 'ambiente', tone: 'from-lime-600 to-zinc-950' },
];

const FALLBACK_ECONOMIC_SCORE: Record<EconomicBucket, number> = {
  estatista: -3.25,
  centro: 0,
  liberal: 3.25,
};

const FALLBACK_PERONISM_SCORE: Record<PeronismBucket, number> = {
  peronista: -3.25,
  centro: 0,
  antiperonista: 3.25,
};

function scoreToPercent(score: number): number {
  const clamped = Math.max(-5, Math.min(5, score));
  return ((clamped + 5) / 10) * 100;
}

function getEconomicScore(portal: PortalSummary): number {
  return portal.aggregate.avg_statism_liberalism ?? FALLBACK_ECONOMIC_SCORE[portal.economic_bucket];
}

function getPeronismScore(portal: PortalSummary): number {
  return portal.aggregate.avg_peronism_antiperonism ?? FALLBACK_PERONISM_SCORE[portal.peronism_bucket];
}

function formatCount(value: number): string {
  return new Intl.NumberFormat('es-AR').format(value);
}

function formatTodayHeader(): string {
  return new Date().toLocaleDateString('es-AR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
}

// ---------------------------------------------------------------------------

function FeaturedStoryCard({ story }: { story: StorySummary }) {
  const hasBlindspot = story.axis_coverage.some((a) => a.blindspots.length > 0);
  return (
    <Link
      to={`/historias/${story.id}`}
      className="group flex flex-col gap-4 rounded-2xl border border-ink/10 bg-white p-6 shadow-sm transition hover:border-accent hover:shadow sm:p-8"
    >
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wider">
        <span className="text-accent">Historia destacada</span>
        <span className="text-ink/30">·</span>
        <span className="text-ink/60">{story.article_count} portales</span>
        {hasBlindspot && (
          <span className="ml-auto rounded-full bg-amber-100 px-3 py-0.5 text-xs font-bold uppercase text-amber-900">
            Blindspot
          </span>
        )}
      </div>
      <h2 className="font-serif text-2xl font-bold leading-snug group-hover:text-accent sm:text-3xl">
        {story.canonical_title}
      </h2>
      <div className="flex flex-col gap-2">
        {story.axis_coverage.map((axis) => (
          <AxisCoverageBar key={axis.axis} axisCoverage={axis} compact />
        ))}
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------

function PortalScatter({ portals }: { portals: PortalSummary[] | null }) {
  const [hovered, setHovered] = useState<{ name: string; x: number; y: number } | null>(null);
  const points = useMemo(
    () =>
      portals
        ? portals.map((p, i) => ({
            slug: p.slug,
            name: p.name,
            x: scoreToPercent(getEconomicScore(p)),
            y: 100 - scoreToPercent(getPeronismScore(p)),
            color: PORTAL_COLORS[i % PORTAL_COLORS.length],
          }))
        : [],
    [portals],
  );

  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-ink/10 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">
            Mapa de medios
          </p>
          <h3 className="font-serif text-base font-bold leading-tight">Dos ejes argentinos</h3>
        </div>
        <Link to="/portales" className="text-xs font-medium text-accent hover:underline">
          ver todos →
        </Link>
      </div>

      <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-ink/40">
        <span>Estatismo</span>
        <span>Liberalismo</span>
      </div>
      <div className="relative h-56 rounded-lg border border-ink/10 sm:h-48">
        <div className="absolute left-1/2 top-0 h-full w-px bg-ink/10" />
        <div className="absolute left-0 top-1/2 h-px w-full bg-ink/10" />
        {/* Mobile: solo etiquetas de eje Y para no pisarse */}
        <div className="pointer-events-none absolute left-1.5 top-1.5 text-[9px] font-semibold uppercase tracking-wider text-ink/40 sm:hidden">
          Antiperonismo
        </div>
        <div className="pointer-events-none absolute bottom-1.5 left-1.5 text-[9px] font-semibold uppercase tracking-wider text-ink/40 sm:hidden">
          Peronismo
        </div>
        {/* Desktop: 4 cuadrantes */}
        <div className="pointer-events-none absolute left-1.5 top-1.5 hidden text-[9px] font-semibold uppercase tracking-wider text-ink/40 sm:block">
          Estat. · Antiperon.
        </div>
        <div className="pointer-events-none absolute right-1.5 top-1.5 hidden text-[9px] font-semibold uppercase tracking-wider text-ink/40 sm:block">
          Lib. · Antiperon.
        </div>
        <div className="pointer-events-none absolute bottom-1.5 left-1.5 hidden text-[9px] font-semibold uppercase tracking-wider text-ink/40 sm:block">
          Estat. · Peronista
        </div>
        <div className="pointer-events-none absolute bottom-1.5 right-1.5 hidden text-[9px] font-semibold uppercase tracking-wider text-ink/40 sm:block">
          Lib. · Peronista
        </div>
        {points.map((p) => (
          <Link
            key={p.slug}
            to={`/portales/${p.slug}`}
            className={`absolute h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${p.color} ring-2 ring-white transition hover:scale-150 hover:ring-accent focus:scale-150 focus:ring-accent focus:outline-none sm:h-2.5 sm:w-2.5`}
            style={{ left: `${p.x}%`, top: `${p.y}%` }}
            onMouseEnter={() => setHovered(p)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(p)}
            onBlur={() => setHovered(null)}
            aria-label={p.name}
          />
        ))}
        {hovered && (
          <div
            className="pointer-events-none absolute z-10 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-ink px-2 py-0.5 text-[10px] font-medium text-paper shadow sm:block"
            style={{
              left: `${hovered.x}%`,
              top: hovered.y < 50 ? `calc(${hovered.y}% + 12px)` : `calc(${hovered.y}% - 24px)`,
            }}
          >
            {hovered.name}
          </div>
        )}
      </div>

      {/* Leyenda visible solo en mobile: linkea cada portal por nombre */}
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 border-t border-ink/10 pt-3 text-xs sm:hidden">
        {points.map((p) => (
          <li key={p.slug} className="min-w-0">
            <Link
              to={`/portales/${p.slug}`}
              className="flex items-center gap-2 truncate text-ink/70 hover:text-accent"
            >
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${p.color}`} />
              <span className="truncate">{p.name}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------

function CategoriesGrid() {
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-ink/10 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">Por tema</p>
          <h3 className="font-serif text-base font-bold leading-tight">Categorías</h3>
        </div>
        <Link to="/categorias" className="text-xs font-medium text-accent hover:underline">
          todas →
        </Link>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {CATEGORIES.map((cat) => (
          <Link
            key={cat.slug}
            to={`/noticias?categoria=${cat.slug}`}
            className={`group relative overflow-hidden rounded-lg bg-gradient-to-br ${cat.tone} px-3 py-2 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:shadow`}
          >
            {cat.name}
          </Link>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function StatsCard({ portals, articleCount }: { portals: PortalSummary[] | null; articleCount: number }) {
  const totalAnalyzed = portals?.reduce((sum, p) => sum + p.aggregate.analyzed_count, 0) ?? 0;
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-ink/10 bg-ink p-4 text-paper shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">Sesgómetro hoy</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-paper/50">Medios</div>
          <div className="font-serif text-2xl font-bold">
            {portals ? formatCount(portals.length) : '…'}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-paper/50">Notas analizadas</div>
          <div className="font-serif text-2xl font-bold">{formatCount(totalAnalyzed)}</div>
        </div>
      </div>
      <p className="text-xs leading-relaxed text-paper/60">
        Analizamos los principales medios argentinos en dos ejes: estatismo/liberalismo y
        peronismo/antiperonismo. {articleCount > 0 && `En esta tanda: ${articleCount} notas recientes.`}
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------

export function HomePage() {
  const [articles, setArticles] = useState<ArticleFeedItem[] | null>(null);
  const [topStory, setTopStory] = useState<StorySummary | null>(null);
  const [portals, setPortals] = useState<PortalSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      listArticles({ limit: 15 }),
      listStories({ limit: 8, only_multi: true }),
      listPortals(),
    ])
      .then(([arts, stories, ports]) => {
        setArticles(arts);
        const featured =
          stories.find((s) => s.axis_coverage.some((a) => a.blindspots.length > 0)) ??
          stories[0] ??
          null;
        setTopStory(featured);
        setPortals(ports);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error cargando el home');
      });
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col items-center gap-4 border-b border-ink/10 pb-8 text-center">
        <img src="/logo.png" alt="Sesgómetro" className="h-20 w-auto sm:h-28" />
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">
          {formatTodayHeader()}
        </p>
        <h1 className="max-w-2xl font-serif text-3xl font-bold leading-tight sm:text-4xl">
          Las noticias del día, con el sesgo medido
        </h1>
        <p className="max-w-xl text-sm leading-relaxed text-ink/60">
          Cada nota viene con su clasificación en los dos ejes argentinos: economía y
          peronismo/antiperonismo.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <main className="flex min-w-0 flex-col gap-6">
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
              {error}
            </div>
          )}

          {topStory && <FeaturedStoryCard story={topStory} />}

          <section className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between border-b border-ink/10 pb-2">
              <h2 className="font-serif text-xl font-bold leading-tight">Últimas noticias</h2>
              <Link to="/historias" className="text-xs font-medium text-accent hover:underline">
                ver historias agrupadas →
              </Link>
            </div>

            {!articles && !error && (
              <ul className="divide-y divide-ink/10">
                {[0, 1, 2, 3, 4].map((i) => (
                  <li key={i} className="animate-pulse py-5 sm:py-6">
                    <div className="mb-2 h-3 w-1/4 rounded bg-ink/10" />
                    <div className="mb-3 h-6 w-3/4 rounded bg-ink/10" />
                    <div className="flex gap-2">
                      <div className="h-4 w-24 rounded-full bg-ink/10" />
                      <div className="h-4 w-24 rounded-full bg-ink/10" />
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {articles && articles.length === 0 && (
              <p className="rounded-xl border border-ink/10 bg-white px-4 py-8 text-center text-sm text-ink/60">
                Aún no hay notas analizadas. El scheduler corre cada 30 minutos.
              </p>
            )}

            {articles && articles.length > 0 && (
              <ul className="divide-y divide-ink/10">
                {articles.map((article) => (
                  <li key={article.id}>
                    <FeedArticleCard article={article} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-6">
          <PortalScatter portals={portals} />
          <CategoriesGrid />
          <StatsCard portals={portals} articleCount={articles?.length ?? 0} />
        </aside>
      </div>
    </div>
  );
}
