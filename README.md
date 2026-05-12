# Sesgometro

Web para analizar la orientacion politica de portales de noticias usando LLM.

Lees un articulo, Sesgometro te dice que sesgo detecta y por que, citando el propio texto. En Argentina lo separa en dos ejes: estatismo/liberalismo y peronismo/antiperonismo.

## Estado

Fase 4/5 en produccion local:

- `/` - home con ultimas noticias
- `/portales` - listado de medios principales con orientacion media
- `/portales/:slug` - detalle por medio con sus ultimos articulos analizados
- `/articulos/:id` - detalle individual
- `/historias` - clusters multi-portal y blindspots
- `/alertas` - alertas de blindspot para usuarios logueados

Backend con SQLite local, scheduler APScheduler que refresca portales, analiza articulos y persiste resultados.

Roadmap completo en [docs/roadmap.md](docs/roadmap.md).

## Stack

- Backend: Python 3.11+, FastAPI, httpx, trafilatura, selectolax, SQLAlchemy, APScheduler, Anthropic SDK
- Frontend: React + TypeScript + Vite + TailwindCSS + React Router

## Arranque rapido

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

API disponible en http://localhost:8000. Docs interactivas en http://localhost:8000/docs.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend en http://localhost:5173.

## Variables de entorno

Ver [backend/.env.example](backend/.env.example). Mientras no haya `ANTHROPIC_API_KEY`, el analizador devuelve un mock determinista basado en el texto del articulo.

## Deploy en Railway

Este repo es un monorepo aislado: backend y frontend se despliegan como dos servicios separados.

### Backend

En Railway, crear un servicio desde el repo y configurar:

- Root Directory: `/backend`
- Config File Path: `/backend/railway.json` si Railway no lo detecta solo
- Healthcheck: `/health`

Variables recomendadas:

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
FRONTEND_ORIGIN=https://TU-FRONTEND.up.railway.app
ANTHROPIC_API_KEY=
JWT_SECRET=un-secreto-largo-y-estable
RUN_INITIAL_REFRESH=true
REFRESH_INTERVAL_MINUTES=180
ARTICLES_PER_PORTAL=5
```

Para datos persistentes, usar Railway Postgres. Si usas SQLite, monta un volume y apunta `DATABASE_URL` a una ruta persistente.

### Frontend

Crear otro servicio desde el mismo repo:

- Root Directory: `/frontend`
- Config File Path: `/frontend/railway.json` si Railway no lo detecta solo

Variable:

```env
VITE_API_BASE_URL=https://TU-BACKEND.up.railway.app
```

Despues de generar el dominio publico del frontend, copia esa URL en `FRONTEND_ORIGIN` del backend y redeploya el backend.
