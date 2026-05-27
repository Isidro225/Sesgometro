import type { AxisId } from '../types';

export type AxisClassification = { label: string; color: string };

export function classifyAxis(axis: AxisId, score: number): AxisClassification {
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
