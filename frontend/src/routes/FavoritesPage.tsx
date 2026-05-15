import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, listFavorites, removeFavorite } from '../lib/api';
import { OrientationBadge } from '../components/OrientationBadge';
import { useAuth } from '../context/AuthContext';
import type { ArticleSummary } from '../types';

export function FavoritesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ArticleSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      setItems(await listFavorites());
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error desconocido');
    }
  };

  useEffect(() => {
    if (user) void load();
  }, [user]);

  const onRemove = async (articleId: number) => {
    try {
      await removeFavorite(articleId);
      setItems((current) => current?.filter((i) => i.id !== articleId) ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error');
    }
  };

  if (!user) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Necesitás{' '}
        <Link to="/login" className="font-medium underline">
          entrar
        </Link>{' '}
        para ver tus favoritos.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="font-serif text-3xl font-bold leading-tight">Mis favoritos</h1>
        <p className="text-ink/70">Artículos de los 10 portales que marcaste con ★.</p>
      </header>

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>
      )}

      {items === null && !error && <p className="text-ink/60">Cargando…</p>}

      {items && items.length === 0 && (
        <div className="rounded-xl border border-ink/10 bg-white px-4 py-8 text-center text-sm text-ink/60">
          Aún no marcaste favoritos. Andá a{' '}
          <Link to="/portales" className="font-medium text-accent hover:underline">
            Portales
          </Link>{' '}
          y tocá la estrella en cualquier artículo.
        </div>
      )}

      {items && items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {items.map((article) => (
            <li
              key={article.id}
              className="flex flex-col gap-2 rounded-xl border border-ink/10 bg-white p-5 transition hover:border-ink/30"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-serif text-lg font-semibold leading-snug hover:text-accent"
                >
                  {article.title || '(Artículo sin titular)'}
                </a>
                {article.analysis && (
                  <div className="flex flex-wrap justify-end gap-1.5">
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
                    {article.analysis.progressivism_conservatism && (
                      <OrientationBadge
                        score={article.analysis.progressivism_conservatism.score}
                        size="sm"
                        axis="progressivism_conservatism"
                      />
                    )}
                  </div>
                )}
              </div>
              {article.analysis && (
                <p className="text-sm text-ink/70">{article.analysis.overall_label}</p>
              )}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink/50">
                {article.author && <span>{article.author}</span>}
                {article.word_count && <span>{article.word_count} palabras</span>}
                <button
                  onClick={() => onRemove(article.id)}
                  className="ml-auto text-red-700 hover:underline"
                >
                  Quitar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
