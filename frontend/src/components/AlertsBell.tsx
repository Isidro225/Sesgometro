import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listAlerts } from '../lib/api';
import { useAuth } from '../context/AuthContext';

const POLL_MS = 60_000;

export function AlertsBell() {
  const { user } = useAuth();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const fetchOnce = () =>
      listAlerts()
        .then((r) => {
          if (!cancelled) setUnread(r.unread_count);
        })
        .catch(() => {
          /* silencioso — el header no debe romperse */
        });
    fetchOnce();
    const id = setInterval(fetchOnce, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [user]);

  if (!user) return null;

  return (
    <Link
      to="/alertas"
      className="relative inline-flex items-center justify-center rounded-lg p-1.5 text-ink/70 transition hover:bg-ink/5 hover:text-ink"
      title={unread > 0 ? `${unread} alerta${unread === 1 ? '' : 's'} sin leer` : 'Alertas'}
      aria-label="Alertas"
    >
      <span className="text-lg leading-none">🔔</span>
      {unread > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white">
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </Link>
  );
}
