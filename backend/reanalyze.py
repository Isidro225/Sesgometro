"""Script de uso único: re-analiza todos los artículos con análisis.

Mantiene el Article (no se reescrapea metadata), solo actualiza el Analysis.
Concurrencia limitada para no saturar rate limits de Anthropic.
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
from app.models import Article


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

        def _save() -> tuple[float, float]:
            with SessionLocal() as session:
                an = session.scalar(
                    select(AnalysisModel).where(AnalysisModel.article_id == article_id)
                )
                if an is None:
                    return (None, None)
                old_per = an.peronism_antiperonism_score
                old_lib = an.statism_liberalism_score
                an.statism_liberalism_score = analysis.statism_liberalism.score
                an.statism_liberalism_label = analysis.statism_liberalism.label
                an.statism_liberalism_justification = analysis.statism_liberalism.justification
                an.libauth_score = analysis.statism_liberalism.score
                an.libauth_label = analysis.statism_liberalism.label
                an.libauth_justification = analysis.statism_liberalism.justification
                an.peronism_antiperonism_score = analysis.peronism_antiperonism.score
                an.peronism_antiperonism_label = analysis.peronism_antiperonism.label
                an.peronism_antiperonism_justification = analysis.peronism_antiperonism.justification
                an.left_right_score = analysis.peronism_antiperonism.score
                an.left_right_label = analysis.peronism_antiperonism.label
                an.left_right_justification = analysis.peronism_antiperonism.justification
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
                return (old_per, old_lib)

        old_per, old_lib = await asyncio.to_thread(_save)
        return {
            "id": article_id,
            "status": "ok",
            "old_per": old_per,
            "new_per": analysis.peronism_antiperonism.score,
            "old_lib": old_lib,
            "new_lib": analysis.statism_liberalism.score,
        }


async def main() -> None:
    with SessionLocal() as session:
        rows = session.execute(
            select(Article.id, Article.url).join(
                AnalysisModel, AnalysisModel.article_id == Article.id
            )
        ).all()
    targets = [(r[0], r[1]) for r in rows]
    print(f"Re-analizando {len(targets)} artículos (concurrencia 4)...")

    sem = asyncio.Semaphore(4)
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
    print(f"\nOK={len(ok)}  FAIL={len(failed)}  tiempo={elapsed:.1f}s")
    print(f"Cambios de signo en peronismo-antiperonismo: {sign_flip_per}")
    for f in failed[:10]:
        print(f"  FAIL {f['id']}: {f['status']} | {f.get('error','')}")


if __name__ == "__main__":
    asyncio.run(main())
