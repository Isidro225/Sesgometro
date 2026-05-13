type Props = {
  score: number;
  leftLabel: string;
  rightLabel: string;
  tone?: 'economic' | 'peronism' | 'legacy';
};

const TONES: Record<NonNullable<Props['tone']>, string> = {
  economic: 'from-red-500 via-gray-200 to-blue-700',
  peronism: 'from-sky-500 via-gray-200 to-violet-500',
  legacy: 'from-red-400 via-gray-200 to-blue-500',
};

export function AxisBar({ score, leftLabel, rightLabel, tone = 'legacy' }: Props) {
  const clamped = Math.max(-5, Math.min(5, score));
  const percent = ((clamped + 5) / 10) * 100;

  return (
    <div>
      <div className="mb-1 flex justify-between text-xs font-medium uppercase tracking-wide text-ink/60">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
      <div className={`relative h-3 rounded-full bg-gradient-to-r ${TONES[tone]}`}>
        <div
          className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-ink shadow"
          style={{ left: `${percent}%` }}
          aria-label={`Puntuación ${score}`}
        />
      </div>
      <div className="mt-1 text-right text-sm font-mono text-ink/70">{score.toFixed(2)}</div>
    </div>
  );
}
