"""Script de uso único: re-analiza todos los artículos con análisis.

Mantiene el Article (no se reescrapea metadata), solo actualiza el Analysis.
Concurrencia limitada para no saturar rate limits de Anthropic.

Tras el último análisis, recomputa `Portal.cultural_bucket` a partir del
promedio de scores en el eje progresismo-conservadurismo para cada portal.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from sqlalchemy import select

from app import analyzer, scraper
from app.db import SessionLocal
from app.models import Analysis as AnalysisModel
from app.models import Article, Portal
from app.refresh import recompute_cultural_bucket


async def reanalyze_one(sem: asyncio.Semaphore, article_id: int, url: str) -> dict:
    async with sem:
        try:
            article_data = await scraper.scrape(url)
        except Exception as exc:
            return {"id": article_id, "status": "scrape_fail", "error": str(exc)[:120]}
        try:
            analysis = await asyncio.to_thread(analyzer.analyze, article_data)
        except Exception as exc:
            return {"id": article_id, "status": "analyze_fail", "error": str(exc)[:120]}

        def _save() -> tuple[float | None, float | None, float | None]:
            with SessionLocal() as session:
                an = session.scalar(
                    select(AnalysisModel).where(AnalysisModel.article_id == article_id)
                )
                if an is None:
                    return (None, None, None)
                old_per = an.peronism_antiperonism_score
                old_lib = an.statism_liberalism_score
                old_cul = an.progressivism_conservatism_score
                an.statism_liberalism_score = analysis.statism_liberalism.score
                an.statism_liberalism_label = analysis.statism_liberalism.label
                an.statism_liberalism_justification = analysis.statism_liberalism.justification
                an.libauth_score = analysis.statism_liberalism.score
                an.libauth_label = analysis.statism_liberalism.label or ""
                an.libauth_justification = analysis.statism_liberalism.justification
                an.peronism_antiperonism_score = analysis.peronism_antiperonism.score
                an.peronism_antiperonism_label = analysis.peronism_antiperonism.label
                an.peronism_antiperonism_justification = analysis.peronism_antiperonism.justification
                an.left_right_score = analysis.peronism_antiperonism.score
                an.left_right_label = analysis.peronism_antiperonism.label or ""
                an.left_right_justification = analysis.peronism_antiperonism.justification
                cul = analysis.progressivism_conservatism
                an.progressivism_conservatism_score = cul.score if cul else None
                an.progressivism_conservatism_label = cul.label if cul else None
                an.progressivism_conservatism_justification = cul.justification if cul else None
                an.emotional_load = analysis.emotional_load
                an.neutral_summary = analysis.neutral_summary
                an.overall_label = analysis.overall_label
                an.confidence = analysis.confidence
                an.framing_json = json.dumps(
                    [f.model_dump() for f in analysis.framing], ensure_ascii=False
                )
                an.model_version_str = analysis.model_version
                an.is_mock = analysis.is_mock
                session.commit()
                return (old_per, old_lib, old_cul)

        old_per, old_lib, old_cul = await asyncio.to_thread(_save)
        cul = analysis.progressivism_conservatism
        return {
            "id": article_id,
            "status": "ok",
            "old_per": old_per,
            "new_per": analysis.peronism_antiperonism.score,
            "old_lib": old_lib,
            "new_lib": analysis.statism_liberalism.score,
            "old_cul": old_cul,
            "new_cul": cul.score if cul else None,
        }


async def main() -> None:
    with SessionLocal() as session:
        rows = session.execute(
            select(Article.id, Article.url).join(
                AnalysisModel, AnalysisModel.article_id == Article.id
            )
        ).all()
    targets = [(r[0], r[1]) for r in rows]
    # Ollama serializa requests; con concurrencia 1 evitamos timeouts en cola.
    # Con Anthropic API se puede subir a 4.
    concurrency = 1
    print(f"Re-analizando {len(targets)} artículos (concurrencia {concurrency})...")

    sem = asyncio.Semaphore(concurrency)
    t0 = time.time()
    results = await asyncio.gather(
        *(reanalyze_one(sem, aid, url) for aid, url in targets)
    )
    elapsed = time.time() - t0

    ok = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] != "ok"]
    sign_flip_per = sum(
        1
        for r in ok
        if r["old_per"] is not None and (r["old_per"] > 0) != (r["new_per"] > 0)
    )
    newly_scored_cultural = sum(
        1 for r in ok if r["old_cul"] is None and r["new_cul"] is not None
    )
    print(f"\nOK={len(ok)}  FAIL={len(failed)}  tiempo={elapsed:.1f}s")
    print(f"Cambios de signo en peronismo-antiperonismo: {sign_flip_per}")
    print(f"Artículos que ahora tienen score cultural (antes null): {newly_scored_cultural}")
    for f in failed[:10]:
        print(f"  FAIL {f['id']}: {f['status']} | {f.get('error','')}")

    # Recomputar cultural_bucket por portal a partir del nuevo promedio.
    def _recompute_all_buckets() -> dict[str, str]:
        out: dict[str, str] = {}
        with SessionLocal() as session:
            for p in session.scalars(select(Portal)).all():
                out[p.slug] = recompute_cultural_bucket(session, p.id)
            session.commit()
        return out

    buckets = await asyncio.to_thread(_recompute_all_buckets)
    print("\nNuevos cultural_bucket por portal:")
    for slug, bucket in sorted(buckets.items()):
        print(f"  {slug:<20} {bucket}")


if __name__ == "__main__":
    asyncio.run(main())
