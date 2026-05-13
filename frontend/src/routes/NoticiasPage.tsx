import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FeedArticleCard } from '../components/FeedArticleCard';
import { ApiError, listArticles } from '../lib/api';
import type { ArticleFeedItem } from '../types';

const CATEGORIES: { slug: string; name: string }[] = [
  { slug: 'politica', name: 'Política' },
  { slug: 'economia', name: 'Economía' },
  { slug: 'seguridad', name: 'Seguridad' },
  { slug: 'internacional', name: 'Internacional' },
  { slug: 'salud', name: 'Salud' },
  { slug: 'ambiente', name: 'Ambiente' },
];

const CATEGORY_NAMES = Object.fromEntries(CATEGORIES.map((c) => [c.slug, c.name]));

export function NoticiasPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const categoriaRaw = searchParams.get('categoria');
  const categoria = categoriaRaw && CATEGORY_NAMES[categoriaRaw] ? categoriaRaw : undefined;
  const categoriaNombre = categoria ? CATEGORY_NAMES[categoria] : null;

  const [articles, setArticles] = useState<ArticleFeedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setArticles(null);
    setError(null);
    listArticles({ limit: 50, categoria })
      .then((data) => {
        if (!cancelled) setArticles(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError || err instanceof Error
              ? err.message
              : 'Error cargando noticias',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [categoria]);

  const setCategoria = (slug: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (slug) {
      next.set('categoria', slug);
    } else {
      next.delete('categoria');
    }
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">
          {categoriaNombre ?? 'Todas las secciones'}
        </p>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="font-serif text-3xl font-bold leading-tight sm:text-4xl">
            {categoriaNombre ? `Noticias · ${categoriaNombre}` : 'Noticias'}
          </h1>
          {categoriaNombre && (
            <button
              type="button"
              onClick={() => setCategoria(null)}
              className="text-sm text-accent hover:underline"
            >
              quitar filtro
            </button>
          )}
        </div>
        <p className="max-w-2xl text-ink/70">
          {categoriaNombre
            ? `Notas individuales clasificadas como "${categoriaNombre}" según keywords del título. Cada una con su sesgo medido en los dos ejes argentinos.`
            : 'Todas las notas analizadas, ordenadas por fecha. Filtrá por categoría para acotar.'}
        </p>
      </header>

      <nav
        className="flex flex-wrap gap-2 border-y border-ink/10 py-3"
        aria-label="Filtros de categoría"
      >
        <button
          type="button"
          onClick={() => setCategoria(null)}
          className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider transition ${
            categoria === undefined
              ? 'bg-ink text-paper'
              : 'border border-ink/15 text-ink/70 hover:border-accent hover:text-accent'
          }`}
        >
          Todas
        </button>
        {CATEGORIES.map((cat) => (
          <button
            key={cat.slug}
            type="button"
            onClick={() => setCategoria(cat.slug)}
            className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider transition ${
              categoria === cat.slug
                ? 'bg-ink text-paper'
                : 'border border-ink/15 text-ink/70 hover:border-accent hover:text-accent'
            }`}
          >
            {cat.name}
          </button>
        ))}
      </nav>

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          {error}
        </div>
      )}

      {articles === null && !error && (
        <ul className="divide-y divide-ink/10">
          {[0, 1, 2, 3, 4, 5].map((i) => (
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
        <div className="rounded-xl border border-ink/10 bg-white px-4 py-8 text-center text-sm text-ink/60">
          {categoriaNombre ? (
            <>
              Aún no hay notas analizadas en "{categoriaNombre}".{' '}
              <button
                type="button"
                onClick={() => setCategoria(null)}
                className="text-accent hover:underline"
              >
                Ver todas
              </button>
              .
            </>
          ) : (
            <>Aún no hay notas analizadas. El scheduler corre cada 30 minutos.</>
          )}
        </div>
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

      {articles && articles.length > 0 && (
        <p className="text-xs text-ink/40">
          Mostrando {articles.length} {articles.length === 1 ? 'nota' : 'notas'}
          {categoriaNombre ? ` en ${categoriaNombre}` : ''} · ordenadas de más reciente a más vieja.
        </p>
      )}

      <div className="border-t border-ink/10 pt-4 text-sm">
        <Link to="/historias" className="text-accent hover:underline">
          ¿Querés ver la misma noticia cubierta por varios portales? Ver historias agrupadas →
        </Link>
      </div>
    </div>
  );
}
