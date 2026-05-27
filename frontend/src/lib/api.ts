import type {
  AlertsResponse,
  ArticleDetail,
  ArticleFeedItem,
  ArticleSummary,
  AuthResponse,
  PortalDetail,
  PortalSummary,
  StoryDetail,
  StorySummary,
  User,
} from '../types';

const TOKEN_KEY = 'sesgometro.token';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export function thumbUrl(originalUrl: string, width: 200 | 400 | 600 | 900 = 400): string {
  return `${API_BASE_URL}/api/img?u=${encodeURIComponent(originalUrl)}&w=${width}`;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null) {
  if (token === null) {
    localStorage.removeItem(TOKEN_KEY);
  } else {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json');
  }
  const token = getStoredToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const data = await response.json();
      if (data?.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

// --- Portales --------------------------------------------------------------

export const listPortals = (): Promise<PortalSummary[]> => request<PortalSummary[]>('/api/portals');

export const getPortal = (slug: string): Promise<PortalDetail> =>
  request<PortalDetail>(`/api/portals/${slug}`);

export const refreshPortal = (slug: string): Promise<{ slug: string; processed: number }> =>
  request(`/api/portals/${slug}/refresh`, { method: 'POST' });

export const refreshAllPortals = (): Promise<{ status: string }> =>
  request('/api/portals/refresh-all', { method: 'POST' });

export const getArticle = (id: number): Promise<ArticleDetail> =>
  request<ArticleDetail>(`/api/articles/${id}`);

export const listArticles = (params?: {
  limit?: number;
  categoria?: string;
}): Promise<ArticleFeedItem[]> => {
  const qs = new URLSearchParams();
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  if (params?.categoria) qs.set('categoria', params.categoria);
  const suffix = qs.toString();
  return request<ArticleFeedItem[]>(`/api/articles${suffix ? `?${suffix}` : ''}`);
};

// --- Auth ------------------------------------------------------------------

export const signup = (email: string, password: string): Promise<AuthResponse> =>
  request<AuthResponse>('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });

export const login = (email: string, password: string): Promise<AuthResponse> =>
  request<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });

export const fetchMe = (): Promise<User> => request<User>('/api/auth/me');

// --- Favoritos -------------------------------------------------------------

export const listFavorites = (): Promise<ArticleSummary[]> =>
  request<ArticleSummary[]>('/api/me/favorites');

export const addFavorite = (articleId: number): Promise<{ added: boolean }> =>
  request<{ added: boolean }>(`/api/me/favorites/${articleId}`, { method: 'POST' });

export const removeFavorite = (articleId: number): Promise<void> =>
  request<void>(`/api/me/favorites/${articleId}`, { method: 'DELETE' });

// --- Historias (Fase 4) ----------------------------------------------------

export const listStories = (params?: {
  limit?: number;
  only_multi?: boolean;
  with_blindspot?: boolean;
  categoria?: string;
}): Promise<StorySummary[]> => {
  const qs = new URLSearchParams();
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  if (params?.only_multi !== undefined) qs.set('only_multi', String(params.only_multi));
  if (params?.with_blindspot !== undefined) qs.set('with_blindspot', String(params.with_blindspot));
  if (params?.categoria) qs.set('categoria', params.categoria);
  const suffix = qs.toString();
  return request<StorySummary[]>(`/api/stories${suffix ? `?${suffix}` : ''}`);
};

export const getStory = (id: number): Promise<StoryDetail> =>
  request<StoryDetail>(`/api/stories/${id}`);

// --- Alertas (Fase 5) ------------------------------------------------------

export const listAlerts = (): Promise<AlertsResponse> => request<AlertsResponse>('/api/me/alerts');

export const markAlertRead = (id: number): Promise<void> =>
  request<void>(`/api/me/alerts/${id}/read`, { method: 'POST' });

export const markAllAlertsRead = (): Promise<void> =>
  request<void>('/api/me/alerts/read-all', { method: 'POST' });

// --- Tracking de visitas ---------------------------------------------------

/** Reporta una navegación (pageview) al backend. Fire-and-forget: nunca lanza
 * ni bloquea la navegación. `path` es la ruta lógica del front. */
export function trackPageview(path: string): void {
  void request<void>('/api/track', {
    method: 'POST',
    body: JSON.stringify({ path, referrer: document.referrer || null }),
  }).catch(() => {
    /* el tracking nunca debe romper la app */
  });
}
