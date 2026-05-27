import type {
  AxisBucket,
  AxisCoverage,
  AxisId,
  BucketCoverage,
  EconomicBucket,
  PeronismBucket,
} from '../types';

type Props = {
  coverage: BucketCoverage[];
  blindspots: AxisBucket[];
  compact?: boolean;
};

type AxisConfig = {
  title: string;
  order: AxisBucket[];
  labels: Record<string, string>;
  colors: Record<string, string>;
  light: Record<string, string>;
};

const LEGACY_CONFIG: AxisConfig = {
  title: 'Izquierda / derecha',
  order: ['izq', 'centro', 'der'],
  labels: {
    izq: 'Izquierda',
    centro: 'Centro',
    der: 'Derecha',
  },
  colors: {
    izq: 'bg-red-500',
    centro: 'bg-gray-400',
    der: 'bg-blue-500',
  },
  light: {
    izq: 'bg-red-50 border-red-200 text-red-900',
    centro: 'bg-gray-100 border-gray-300 text-gray-800',
    der: 'bg-blue-50 border-blue-200 text-blue-900',
  },
};

const AXIS_CONFIG: Record<AxisId, AxisConfig> = {
  statism_liberalism: {
    title: 'Estatismo / liberalismo',
    order: ['estatista', 'centro', 'liberal'],
    labels: {
      estatista: 'Estatismo',
      centro: 'Centro',
      liberal: 'Liberalismo',
    },
    colors: {
      estatista: 'bg-red-500',
      centro: 'bg-gray-400',
      liberal: 'bg-blue-700',
    },
    light: {
      estatista: 'bg-red-50 border-red-200 text-red-900',
      centro: 'bg-gray-100 border-gray-300 text-gray-800',
      liberal: 'bg-blue-50 border-blue-200 text-blue-900',
    },
  },
  peronism_antiperonism: {
    title: 'Peronismo / antiperonismo',
    order: ['peronista', 'centro', 'antiperonista'],
    labels: {
      peronista: 'Peronismo',
      centro: 'Centro',
      antiperonista: 'Antiperonismo',
    },
    colors: {
      peronista: 'bg-sky-500',
      centro: 'bg-gray-400',
      antiperonista: 'bg-violet-500',
    },
    light: {
      peronista: 'bg-sky-50 border-sky-200 text-sky-900',
      centro: 'bg-gray-100 border-gray-300 text-gray-800',
      antiperonista: 'bg-violet-50 border-violet-200 text-violet-900',
    },
  },
};

function inferConfig(bucket: AxisBucket): AxisConfig {
  if (bucket === 'estatista' || bucket === 'liberal') return AXIS_CONFIG.statism_liberalism;
  if (bucket === 'peronista' || bucket === 'antiperonista') return AXIS_CONFIG.peronism_antiperonism;
  return LEGACY_CONFIG;
}

function labelFor(config: AxisConfig, bucket: AxisBucket): string {
  return config.labels[bucket] ?? String(bucket);
}

function classFor(config: AxisConfig, bucket: AxisBucket, kind: 'colors' | 'light'): string {
  return config[kind][bucket] ?? LEGACY_CONFIG[kind].centro;
}

function CoverageBar({ coverage, blindspots, compact = false, config }: Props & { config: AxisConfig }) {
  const total = coverage.reduce((sum, c) => sum + c.article_count, 0);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-ink/10">
        {config.order.map((bucket) => {
          const c = coverage.find((x) => x.bucket === bucket);
          const count = c?.article_count ?? 0;
          const width = total > 0 ? (count / total) * 100 : 0;
          return (
            <div
              key={bucket}
              className={`${classFor(config, bucket, 'colors')} ${count === 0 ? 'opacity-30' : ''} h-full transition-all`}
              style={{ width: `${width}%` }}
              title={`${labelFor(config, bucket)}: ${count} artículos`}
            />
          );
        })}
      </div>
      {!compact && (
        <div className="grid grid-cols-3 gap-2 text-xs">
          {config.order.map((bucket) => {
            const c = coverage.find((x) => x.bucket === bucket);
            const portalCount = c?.portal_count ?? 0;
            const articleCount = c?.article_count ?? 0;
            const isBlindspot = blindspots.includes(bucket);
            return (
              <div
                key={bucket}
                className={`rounded-lg border px-2 py-1.5 ${classFor(config, bucket, 'light')} ${
                  isBlindspot ? 'opacity-50' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-semibold uppercase tracking-wide">
                    {labelFor(config, bucket)}
                  </span>
                  {isBlindspot && (
                    <span className="rounded bg-amber-200 px-1 text-[10px] font-bold uppercase text-amber-900">
                      Blindspot
                    </span>
                  )}
                </div>
                <div className="mt-0.5 font-mono">
                  {articleCount} art · {portalCount} medio{portalCount === 1 ? '' : 's'}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function BlindspotBar({ coverage, blindspots, compact = false }: Props) {
  return (
    <CoverageBar
      coverage={coverage}
      blindspots={blindspots}
      compact={compact}
      config={LEGACY_CONFIG}
    />
  );
}

export function AxisCoverageBar({ axisCoverage, compact = false }: { axisCoverage: AxisCoverage; compact?: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      <div
        className={`font-semibold uppercase tracking-wider text-ink/50 ${
          compact ? 'text-[10px]' : 'text-xs'
        }`}
      >
        {AXIS_CONFIG[axisCoverage.axis].title}
      </div>
      <CoverageBar
        coverage={axisCoverage.coverage}
        blindspots={axisCoverage.blindspots}
        compact={compact}
        config={AXIS_CONFIG[axisCoverage.axis]}
      />
    </div>
  );
}

export function BucketPill({ bucket, axis }: { bucket: AxisBucket; axis?: AxisId }) {
  const config = axis ? AXIS_CONFIG[axis] : inferConfig(bucket);
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${classFor(
        config,
        bucket,
        'light',
      )}`}
    >
      {labelFor(config, bucket)}
    </span>
  );
}

export function PortalAxisPills({
  economicBucket,
  peronismBucket,
}: {
  economicBucket: EconomicBucket;
  peronismBucket: PeronismBucket;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <BucketPill bucket={economicBucket} axis="statism_liberalism" />
      <BucketPill bucket={peronismBucket} axis="peronism_antiperonism" />
    </div>
  );
}
