import type { AxisId } from '../types';

type Props = {
  score: number | null;
  size?: 'sm' | 'md' | 'lg';
  axis?: AxisId;
};

function classifyAxis(axis: AxisId, score: number): { label: string; color: string } {
  if (axis === 'statism_liberalism') {
    if (score <= -3) return { label: 'Estatismo marcado', color: 'bg-red-600 text-white' };
    if (score <= -1) return { label: 'Más Estado', color: 'bg-red-100 text-red-900' };
    if (score < 1) return { label: 'Centro / neutro', color: 'bg-gray-200 text-gray-800' };
    if (score < 3) return { label: 'Liberal moderado', color: 'bg-blue-100 text-blue-900' };
    return { label: 'Liberal marcado', color: 'bg-blue-700 text-white' };
  }

  if (score <= -3) return { label: 'Peronismo marcado', color: 'bg-sky-600 text-white' };
  if (score <= -1) return { label: 'Afinidad peronista', color: 'bg-sky-100 text-sky-900' };
  if (score < 1) return { label: 'No alineado', color: 'bg-gray-200 text-gray-800' };
  if (score < 3) return { label: 'Antiperonismo moderado', color: 'bg-violet-100 text-violet-900' };
  return { label: 'Antiperonismo marcado', color: 'bg-violet-600 text-white' };
}

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
