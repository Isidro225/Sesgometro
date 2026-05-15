export type AxisScore = {
  score: number;
  /** Legacy. El UI lo deriva del score via classifyAxis(). Puede venir null en análisis nuevos. */
  label: string | null;
  justification: string;
};

export type FramingFinding = {
  kind: 'emphasis' | 'omission' | 'loaded_language' | 'source_selection';
  description: string;
  quote?: string | null;
};

export type Analysis = {
  statism_liberalism: AxisScore;
  peronism_antiperonism: AxisScore;
  /** Análisis previos a 2026-05-15 no tienen este eje (queda null). */
  progressivism_conservatism: AxisScore | null;
  emotional_load: number;
  framing: FramingFinding[];
  neutral_summary: string;
  overall_label: string;
  confidence: number;
  model_version: string;
  is_mock: boolean;
};

export type ScrapedArticle = {
  url: string;
  title: string | null;
  author: string | null;
  site_name: string | null;
  published_at: string | null;
  text: string;
  word_count: number;
  image_url?: string | null;
};

export type BiasBucket = 'izq' | 'centro' | 'der';
export type EconomicBucket = 'estatista' | 'centro' | 'liberal';
export type PeronismBucket = 'peronista' | 'centro' | 'antiperonista';
export type CulturalBucket = 'progresista' | 'centro' | 'conservador';
export type AxisId =
  | 'statism_liberalism'
  | 'peronism_antiperonism'
  | 'progressivism_conservatism';
export type AxisBucket = EconomicBucket | PeronismBucket | CulturalBucket | BiasBucket;

export type PortalAggregate = {
  avg_statism_liberalism: number | null;
  avg_peronism_antiperonism: number | null;
  avg_progressivism_conservatism: number | null;
  avg_emotional_load: number | null;
  article_count: number;
  analyzed_count: number;
  avg_left_right?: number | null;
  avg_libauth?: number | null;
};

export type PortalSummary = {
  slug: string;
  name: string;
  homepage_url: string;
  description: string | null;
  bias_bucket: BiasBucket;
  economic_bucket: EconomicBucket;
  peronism_bucket: PeronismBucket;
  cultural_bucket: CulturalBucket;
  last_refreshed_at: string | null;
  aggregate: PortalAggregate;
};

export type ArticleSummary = {
  id: number;
  url: string;
  title: string | null;
  author: string | null;
  published_at: string | null;
  word_count: number | null;
  discovered_at: string;
  analysis: Analysis | null;
  is_favorite: boolean;
  image_url?: string | null;
};

export type PortalDetail = PortalSummary & {
  articles: ArticleSummary[];
};

export type ArticleFeedItem = {
  id: number;
  title: string | null;
  url: string;
  discovered_at: string;
  published_at: string | null;
  portal_slug: string;
  portal_name: string;
  bias_bucket: BiasBucket;
  economic_bucket: EconomicBucket;
  peronism_bucket: PeronismBucket;
  cultural_bucket: CulturalBucket;
  overall_label: string | null;
  statism_liberalism_score: number | null;
  peronism_antiperonism_score: number | null;
  progressivism_conservatism_score: number | null;
  emotional_load: number | null;
  is_mock: boolean;
  story_id: number | null;
  image_url?: string | null;
};

export type ArticlePortalRef = {
  slug: string;
  name: string;
  bias_bucket: BiasBucket;
  economic_bucket: EconomicBucket;
  peronism_bucket: PeronismBucket;
  cultural_bucket: CulturalBucket;
};

export type ArticleDetail = {
  article: ScrapedArticle;
  analysis: Analysis | null;
  is_favorite: boolean;
  portal: ArticlePortalRef;
  story_id: number | null;
};

// ---------------------------------------------------------------------------
// Auth (Fase 3)
// ---------------------------------------------------------------------------

export type User = {
  id: number;
  email: string;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: 'bearer';
  user: User;
};

// ---------------------------------------------------------------------------
// Stories + blindspot (Fase 4)
// ---------------------------------------------------------------------------

export type BucketCoverage = {
  bucket: AxisBucket;
  portal_count: number;
  article_count: number;
  sample_portals: string[];
};

export type AxisCoverage = {
  axis: AxisId;
  coverage: BucketCoverage[];
  blindspots: AxisBucket[];
};

export type StoryArticle = {
  article_id: number;
  portal_slug: string;
  portal_name: string;
  bias_bucket: BiasBucket;
  economic_bucket: EconomicBucket;
  peronism_bucket: PeronismBucket;
  cultural_bucket: CulturalBucket;
  title: string | null;
  url: string;
  published_at: string | null;
  overall_label: string | null;
  statism_liberalism_score: number | null;
  peronism_antiperonism_score: number | null;
  progressivism_conservatism_score: number | null;
  left_right_score?: number | null;
};

export type StorySummary = {
  id: number;
  canonical_title: string;
  article_count: number;
  first_seen_at: string;
  last_seen_at: string;
  axis_coverage: AxisCoverage[];
  coverage: BucketCoverage[];
  blindspots: AxisBucket[];
};

export type StoryDetail = StorySummary & {
  articles: StoryArticle[];
};

// ---------------------------------------------------------------------------
// Alertas (Fase 5)
// ---------------------------------------------------------------------------

export type AlertItem = {
  id: number;
  kind: 'blindspot';
  created_at: string;
  read: boolean;
  story_id: number | null;
  story_title: string | null;
  blindspots: AxisBucket[];
  axis_blindspots: AxisCoverage[];
  article_count: number;
};

export type AlertsResponse = {
  unread_count: number;
  items: AlertItem[];
};
