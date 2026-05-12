import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AxisCoverageBar } from '../components/BlindspotBar';
import { ApiError, listStories } from '../lib/api';
import type { StorySummary } from '../types';

const CATEGORY_NAMES: Record<string, string> = {
  politica: 'Política',
  economia: 'Economía',
  seguridad: 'Seguridad',
  internacional: 'Internacional',
  salud: 'Salud',
  ambiente: 'Ambiente',
};

export function StoriesPage() {
  const [searchParams] = useSearchParams();
  const categoriaRaw = searchParams.get('categoria');
  const categoria = categoriaRaw && CATEGORY_NAMES[categoriaRaw] ? categoriaRaw : undefined;
  const categoriaNombre = categoria ? CATEGORY_NAMES[categoria] : null;

  const [stories, setStories] = useState<StorySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyBlindspot, setOnlyBlindspot] = useState(false);

  const load = async () => {
    try {
      setError(null);
      setStories(null);
      setStories(
        await listStories({
          limit: 50,
          only_multi: true,
          with_blindspot: onlyBlindspot,
          categoria,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Error desconocido');
    }
  };

  useEffect(() => {
    void load();
  }, [onlyBlindspot, categoria]);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="font-serif text-3xl font-bold leading-tight">
            {categoriaNombre ? `Historias · ${categoriaNombre}` : 'Historias'}
          </h1>
          {categoriaNombre && (
            <Link to="/historias" className="text-sm text-accent hover:underline">
              quitar filtro
            </Link>
          )}
        </div>
        <p className="max-w-2xl text-ink/70">
          {categoriaNombre
            ? `Historias clasificadas como "${categoriaNombre}" según keywords del título. Mirá si falta cobertura en alguno de los ejes argentinos.`
            : 'La misma noticia agrupada según la cubrieron distintos portales. Mirá si falta cobertura en alguno de los dos ejes argentinos: estatismo/liberalismo o peronismo/antiperonismo.'}
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-ink/10 bg-white px-4 py-3 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={onlyBlindspot}
            onChange={(e) => setOnlyBlindspot(e.target.checked)}
          />
          Solo historias con blindspot
        </label>
      </div>

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>
      )}

      {stories === null && !error && <p className="text-ink/60">Cargando…</p>}

      {stories && stories.length === 0 && (
        <div className="rounded-xl border border-ink/10 bg-white px-4 py-8 text-center text-sm text-ink/60">
          {categoriaNombre
            ? `Aún no hay historias en "${categoriaNombre}". Probá con otra categoría o quitá el filtro.`
            : onlyBlindspot
            ? 'Ninguna historia tiene blindspots por ahora. Probá quitando el filtro.'
            : 'Aún no hay clusters multi-portal. Esperá a que el scheduler recoja más artículos.'}
        </div>
      )}

      {stories && stories.length > 0 && (
        <ul className="flex flex-col gap-4">
          {stories.map((story) => (
            <li key={story.id}>
              <Link
                to={`/historias/${story.id}`}
                className="group flex flex-col gap-3 rounded-2xl border border-ink/10 bg-white p-5 transition hover:border-accent hover:shadow"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <h2 className="font-serif text-lg font-bold leading-snug group-hover:text-accent">
                    {story.canonical_title}
                  </h2>
                  {story.axis_coverage.some((axis) => axis.blindspots.length > 0) && (
                    <span className="rounded-full bg-amber-100 px-3 py-0.5 text-xs font-bold uppercase text-amber-900">
                      Blindspot
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  {story.axis_coverage.map((axis) => (
                    <AxisCoverageBar key={axis.axis} axisCoverage={axis} compact />
                  ))}
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink/60">
                  <span>{story.article_count} artículos</span>
                  <span>
                    {new Date(story.first_seen_at).toLocaleDateString('es-AR')} —{' '}
                    {new Date(story.last_seen_at).toLocaleDateString('es-AR')}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
