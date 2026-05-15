import { Link } from 'react-router-dom';
import { ArticleThumbnail } from './ArticleThumbnail';
import { OrientationBadge } from './OrientationBadge';
import type { ArticleFeedItem } from '../types';

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 0) return 'ahora';
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'ahora';
  if (mins < 60) return `hace ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs} h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `hace ${days} d`;
  return date.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' });
}

export function FeedArticleCard({ article }: { article: ArticleFeedItem }) {
  const when = timeAgo(article.published_at ?? article.discovered_at);
  return (
    <article className="group flex flex-col gap-3 py-5 transition sm:flex-row sm:gap-5 sm:py-6">
      {article.image_url && (
        <Link to={`/articulos/${article.id}`} className="block sm:w-44 sm:flex-shrink-0">
          <ArticleThumbnail
            imageUrl={article.image_url}
            siteName={article.portal_name}
            width={400}
            className="aspect-[16/9] w-full overflow-hidden rounded-lg bg-ink/5"
          />
        </Link>
      )}
      <div className="flex w-full min-w-0 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          <Link
            to={`/portales/${article.portal_slug}`}
            className="font-semibold uppercase tracking-wider text-accent hover:underline"
          >
            {article.portal_name}
          </Link>
          <span className="text-ink/30">·</span>
          <span className="text-ink/50">{when}</span>
          {article.is_mock && (
            <span className="rounded-full bg-ink/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-ink/60">
              Mock
            </span>
          )}
        </div>
        <Link
          to={`/articulos/${article.id}`}
          className="font-serif text-xl font-bold leading-snug text-ink group-hover:text-accent"
        >
          {article.title ?? '(Sin título)'}
        </Link>
        <div className="flex flex-wrap gap-1.5">
          <OrientationBadge
            score={article.statism_liberalism_score}
            axis="statism_liberalism"
            size="sm"
          />
          <OrientationBadge
            score={article.peronism_antiperonism_score}
            axis="peronism_antiperonism"
            size="sm"
          />
          {article.progressivism_conservatism_score !== null && (
            <OrientationBadge
              score={article.progressivism_conservatism_score}
              axis="progressivism_conservatism"
              size="sm"
            />
          )}
        </div>
      </div>
    </article>
  );
}
