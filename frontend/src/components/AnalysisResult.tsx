import type { Analysis, FramingFinding, ScrapedArticle } from '../types';
import { classifyAxis } from '../lib/axisLabels';
import { ArticleThumbnail } from './ArticleThumbnail';
import { AxisBar } from './AxisBar';

const FRAMING_LABELS: Record<FramingFinding['kind'], string> = {
  emphasis: 'Énfasis desproporcionado',
  omission: 'Omisión relevante',
  loaded_language: 'Lenguaje cargado',
  source_selection: 'Selección de fuentes',
};

type Props = {
  data: { article: ScrapedArticle; analysis: Analysis };
};

export function AnalysisResult({ data }: Props) {
  const { article, analysis } = data;

  return (
    <article className="flex flex-col gap-8 rounded-2xl border border-ink/10 bg-white p-6 shadow-sm sm:p-8">
      {analysis.is_mock && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Modo mock activo.</strong> Estás viendo un análisis simulado determinista. Configura{' '}
          <code className="font-mono">ANTHROPIC_API_KEY</code> en <code className="font-mono">backend/.env</code> para
          activar Claude.
        </div>
      )}

      <header className="flex flex-col gap-4 border-b border-ink/10 pb-6 sm:flex-row-reverse sm:items-start sm:gap-6">
        {article.image_url && (
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full sm:w-2/5 sm:flex-shrink-0"
          >
            <ArticleThumbnail
              imageUrl={article.image_url}
              siteName={article.site_name}
              width={600}
              className="aspect-[16/9] w-full overflow-hidden rounded-xl bg-ink/5"
            />
            <div className="mt-1 text-xs text-ink/50">
              Foto: {article.site_name || new URL(article.url).hostname}
            </div>
          </a>
        )}
        <div className="flex min-w-0 flex-col gap-3 sm:flex-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-accent">
            {article.site_name || new URL(article.url).hostname}
          </div>
          <h2 className="font-serif text-2xl font-bold leading-snug sm:text-3xl">
            {article.title || '(Artículo sin titular)'}
          </h2>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink/60">
            {article.author && <span>{article.author}</span>}
            {article.published_at && <span>{new Date(article.published_at).toLocaleDateString('es-ES')}</span>}
            <span>{article.word_count} palabras</span>
            <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
              ver original ↗
            </a>
          </div>
          <div className="mt-2 flex flex-col gap-2 border-t border-ink/10 pt-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-ink/50">Veredicto</div>
            <p className="text-xl font-semibold leading-tight sm:text-2xl">{analysis.overall_label}</p>
            <div className="text-sm text-ink/60">
              Confianza: <strong className="text-ink">{(analysis.confidence * 100).toFixed(0)}%</strong>
            </div>
          </div>

          <div className="flex flex-col gap-4 border-t border-ink/10 pt-4">
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/50">Estatismo – Liberalismo</h3>
              <AxisBar
                score={analysis.statism_liberalism.score}
                leftLabel="Estatismo"
                rightLabel="Liberalismo"
                tone="economic"
              />
              <p className="text-sm font-medium">
                {classifyAxis('statism_liberalism', analysis.statism_liberalism.score).label}
              </p>
              <p className="text-sm leading-relaxed text-ink/70">{analysis.statism_liberalism.justification}</p>
            </div>

            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/50">Peronismo – Antiperonismo</h3>
              <AxisBar
                score={analysis.peronism_antiperonism.score}
                leftLabel="Peronismo"
                rightLabel="Antiperonismo"
                tone="peronism"
              />
              <p className="text-sm font-medium">
                {classifyAxis('peronism_antiperonism', analysis.peronism_antiperonism.score).label}
              </p>
              <p className="text-sm leading-relaxed text-ink/70">
                {analysis.peronism_antiperonism.justification}
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/50">Progresismo – Conservadurismo</h3>
              <AxisBar
                score={analysis.progressivism_conservatism?.score ?? null}
                leftLabel="Progresismo"
                rightLabel="Conservadurismo"
                tone="cultural"
              />
              {analysis.progressivism_conservatism ? (
                <>
                  <p className="text-sm font-medium">
                    {classifyAxis(
                      'progressivism_conservatism',
                      analysis.progressivism_conservatism.score,
                    ).label}
                  </p>
                  <p className="text-sm leading-relaxed text-ink/70">
                    {analysis.progressivism_conservatism.justification}
                  </p>
                </>
              ) : (
                <p className="text-sm italic text-ink/50">
                  Eje no evaluado (análisis previo a la incorporación del eje cultural).
                </p>
              )}
            </div>
          </div>
        </div>
      </header>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-ink/50">Carga emocional</h3>
        <div className="h-3 w-full rounded-full bg-ink/10">
          <div
            className="h-3 rounded-full bg-gradient-to-r from-emerald-400 to-rose-500"
            style={{ width: `${analysis.emotional_load * 100}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-ink/60">
          <span>Informativo</span>
          <span className="font-mono">{(analysis.emotional_load * 100).toFixed(0)}%</span>
          <span>Editorial cargado</span>
        </div>
      </section>

      {analysis.framing.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-ink/50">Hallazgos de framing</h3>
          <ul className="flex flex-col gap-3">
            {analysis.framing.map((finding, idx) => (
              <li key={idx} className="rounded-lg border-l-4 border-accent bg-ink/[0.02] p-4">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent">
                  {FRAMING_LABELS[finding.kind]}
                </div>
                <p className="text-sm leading-relaxed">{finding.description}</p>
                {finding.quote && (
                  <blockquote className="mt-2 border-l-2 border-ink/20 pl-3 font-serif text-sm italic text-ink/70">
                    «{finding.quote}»
                  </blockquote>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-2 rounded-xl bg-ink/[0.03] p-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-ink/50">Resumen neutro</h3>
        <p className="font-serif text-base leading-relaxed text-ink/90">{analysis.neutral_summary}</p>
      </section>
    </article>
  );
}
