import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { trackPageview } from '../lib/api';

/** Reporta un pageview cada vez que cambia la ruta. No renderiza nada.
 * Debe montarse dentro del Router. En dev con StrictMode el efecto corre dos
 * veces (doble pageview); en el build de producción corre una sola vez. */
export function PageTracker() {
  const location = useLocation();
  useEffect(() => {
    trackPageview(location.pathname);
  }, [location.pathname]);
  return null;
}
