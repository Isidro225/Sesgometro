import type { AxisId } from '../types';
import { classifyAxis } from '../lib/axisLabels';

type Props = {
  score: number | null;
  size?: 'sm' | 'md' | 'lg';
  axis?: AxisId;
};

const SIZES = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
  lg: 'px-4 py-1.5 text-base',
};

export function OrientationBadge({ score, size = 'md', axis = 'peronism_antiperonism' }: Props) {
  if (score === null) {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full bg-ink/10 text-ink/60 ${SIZES[size]}`}>
        sin datos
      </span>
    );
  }
  const { label, color } = classifyAxis(axis, score);
  return (
    <span className={`inline-flex items-center gap-2 rounded-full font-medium ${color} ${SIZES[size]}`}>
      <span>{label}</span>
      {size !== 'sm' && (
        <span className="font-mono text-[0.85em] opacity-80">{score.toFixed(2)}</span>
      )}
    </span>
  );
}
