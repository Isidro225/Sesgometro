import { Link } from 'react-router-dom';

const TOPICS = [
  {
    name: 'Política',
    slug: 'politica',
    eyebrow: 'Poder público',
    description: 'Gobierno, Congreso, campañas y disputas partidarias.',
    tone: 'from-red-500 via-zinc-800 to-slate-900',
    bars: ['w-10 bg-white/75', 'w-20 bg-white/30', 'w-14 bg-white/60'],
  },
  {
    name: 'Economía',
    slug: 'economia',
    eyebrow: 'Bolsillo',
    description: 'Inflación, actividad, mercados y costo de vida.',
    tone: 'from-emerald-600 via-teal-800 to-slate-900',
    bars: ['w-16 bg-white/40', 'w-8 bg-white/75', 'w-24 bg-white/50'],
  },
  {
    name: 'Seguridad',
    slug: 'seguridad',
    eyebrow: 'Agenda urbana',
    description: 'Delito, fuerzas federales, justicia y territorio.',
    tone: 'from-sky-700 via-cyan-900 to-zinc-900',
    bars: ['w-12 bg-white/60', 'w-24 bg-white/30', 'w-9 bg-white/75'],
  },
  {
    name: 'Internacional',
    slug: 'internacional',
    eyebrow: 'Mundo',
    description: 'Conflictos, elecciones, diplomacia y región.',
    tone: 'from-indigo-600 via-blue-900 to-stone-900',
    bars: ['w-20 bg-white/50', 'w-10 bg-white/75', 'w-16 bg-white/40'],
  },
  {
    name: 'Salud',
    slug: 'salud',
    eyebrow: 'Sociedad',
    description: 'Sistema sanitario, ciencia médica y políticas públicas.',
    tone: 'from-rose-500 via-fuchsia-900 to-slate-950',
    bars: ['w-14 bg-white/70', 'w-24 bg-white/30', 'w-12 bg-white/50'],
  },
  {
    name: 'Ambiente',
    slug: 'ambiente',
    eyebrow: 'Clima',
    description: 'Energía, producción, ciudades y recursos naturales.',
    tone: 'from-lime-600 via-green-900 to-zinc-950',
    bars: ['w-8 bg-white/75', 'w-16 bg-white/50', 'w-24 bg-white/30'],
  },
];

export function CategoriesPage() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">Categorías</p>
          <h1 className="font-serif text-3xl font-bold leading-tight sm:text-4xl">
            Agendas para mirar en paralelo
          </h1>
        </div>
        <Link
          to="/noticias"
          className="rounded-lg border border-ink/15 px-4 py-2 text-sm font-medium text-ink/70 transition hover:border-accent hover:text-accent"
        >
          Ver todas las noticias
        </Link>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TOPICS.map((topic) => (
          <Link
            key={topic.slug}
            to={`/noticias?categoria=${topic.slug}`}
            className={`group relative min-h-52 overflow-hidden rounded-2xl bg-gradient-to-br ${topic.tone} p-5 text-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg`}
          >
            <div className="absolute inset-x-5 top-5 flex flex-col items-end gap-2 opacity-80">
              {topic.bars.map((bar, index) => (
                <span key={index} className={`h-2 rounded-full ${bar}`} />
              ))}
            </div>
            <div className="relative z-10 flex h-full min-h-44 flex-col justify-end gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-white/70">
                {topic.eyebrow}
              </span>
              <h2 className="font-serif text-2xl font-bold leading-tight">{topic.name}</h2>
              <p className="max-w-xs text-sm leading-relaxed text-white/80">{topic.description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
