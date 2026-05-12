# Roadmap Sesgómetro

| Fase | Entregable | Estado |
|---|---|---|
| 1 | Monorepo, endpoint `/analyze` con scraping + Claude (o mock), frontend con input + vista de resultado. Sin BD. | Hecho |
| 2 | SQLite + catálogo de 10 medios, descubrimiento de artículos por portada, scheduler cada 30 min, vistas `/portales` y `/portales/:slug` con score agregado | Hecho |
| 3 | Auth JWT, historial por usuario, favoritos | Hecho |
| 4 | Embeddings TF sparse, clustering de eventos, **blindspot estilo Ground News** | Hecho |
| 5 | Alertas, deriva ideológica temporal, notificaciones | Pendiente |

## Portales seed (Fase 2)

Clarín, La Nación, Infobae, Página/12, TN, Perfil, Ámbito, El Cronista, Tiempo Argentino, La Voz del Interior.

## Análisis: qué pide Sesgómetro a Claude

- Eje estatismo-liberalismo (-5 a +5) con justificación
- Eje peronismo-antiperonismo (-5 a +5)
- Carga emocional (0-1): editorializado vs informativo
- Sesgo de framing: qué se omite, qué se enfatiza
- Resumen neutro del hecho
- Citas concretas del artículo que sostienen cada puntuación

Prompt cacheado en `system`. `claude-opus-4-7` para análisis profundo, `claude-haiku-4-5-20251001` para pre-screening cuando aplique.

## Notas legales del scraping

- Respetar `robots.txt`
- Rate limiting (1 req cada 5-10s por dominio)
- Almacenar análisis + URL, no republicar texto íntegro
- User-Agent identificable, contacto opt-out
