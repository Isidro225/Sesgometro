import { useState } from 'react';
import { addFavorite, removeFavorite } from '../lib/api';
import { useAuth } from '../context/AuthContext';

type Props = {
  articleId: number;
  initial: boolean;
};

export function FavoriteButton({ articleId, initial }: Props) {
  const { user } = useAuth();
  const [fav, setFav] = useState(initial);
  const [busy, setBusy] = useState(false);

  if (!user) return null;

  const toggle = async () => {
    setBusy(true);
    try {
      if (fav) {
        await removeFavorite(articleId);
        setFav(false);
      } else {
        await addFavorite(articleId);
        setFav(true);
      }
    } catch {
      // silencioso — el estado vuelve por sí mismo si se recarga la página
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={toggle}
      disabled={busy}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition disabled:opacity-50 ${
        fav
          ? 'border-amber-400 bg-amber-50 text-amber-900'
          : 'border-ink/15 bg-white text-ink/70 hover:border-amber-400 hover:text-amber-900'
      }`}
      aria-pressed={fav}
      title={fav ? 'Quitar de favoritos' : 'Marcar como favorito'}
    >
      <span className="text-base leading-none">{fav ? '★' : '☆'}</span>
      <span>{fav ? 'Favorito' : 'Favorito'}</span>
    </button>
  );
}
