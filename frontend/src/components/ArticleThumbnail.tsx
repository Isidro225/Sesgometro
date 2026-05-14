import { useState } from 'react';
import { thumbUrl } from '../lib/api';

type Props = {
  imageUrl: string | null | undefined;
  siteName: string | null | undefined;
  width?: 200 | 400 | 600 | 900;
  /** Tailwind classes para el contenedor (controla aspect/size). */
  className?: string;
};

/**
 * Thumbnail proxied through /api/img: resize + cache + host whitelist.
 * If the original URL is missing or fails to load, returns null silently.
 * Crédito al medio se renderiza por separado en cada card; acá sólo el tag <img>.
 */
export function ArticleThumbnail({ imageUrl, siteName, width = 400, className }: Props) {
  const [failed, setFailed] = useState(false);
  if (!imageUrl || failed) return null;
  return (
    <div className={className ?? 'aspect-[16/9] w-full overflow-hidden rounded-lg bg-ink/5'}>
      <img
        src={thumbUrl(imageUrl, width)}
        alt={siteName ? `Foto: ${siteName}` : ''}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
        className="h-full w-full object-cover"
      />
    </div>
  );
}
