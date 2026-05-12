"""Reintento secuencial con backoff para los IDs que fallaron en reanalyze.py.

Concurrencia 1, retry exponencial ante 429 (rate limit) y errores transitorios.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

from anthropic import APIStatusError
from sqlalchemy import select

from app import analyzer, scraper
from app.db import SessionLocal
from app.models import Analysis as AnalysisModel
from app.models import Article

FAILED_IDS = [58, 68, 69, 89, 96, 97, 114, 118, 123, 132, 139, 145, 146, 156, 158, 180, 194, 197, 212, 214, 222]


async def analyze_with_retry(article_data, max_retries: int = 4):
    delay = 5
    for attempt in range(max_retries):
        try:
            return await asyncio.to_thread(analyzer.analyze, article_data)
        except APIStatusError as exc:
            if exc.status_code == 429 and attempt < max_retries - 1:
                print(f"    429 rate limit, esperando {delay}s (intento {attempt+1}/{max_retries})", flush=True)
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise


async def main() -> None:
    print(f"Reintentando {len(FAILED_IDS)} artículos (secuencial, backoff)...", flush=True)

    with SessionLocal() as session:
        rows = session.execute(
            select(Article.id, Article.url).where(Article.id.in_(FAILED_IDS))
        ).all()
    targets = [(r[0], r[1]) for r in rows]

    ok, fail = 0, 0
    t0 = time.time()
    for aid, url in targets:
        try:
            article_data = await scraper.scrape(url)
        except Exception as exc:
            print(f"  id={aid} scrape_fail: {str(exc)[:120]}", flush=True)
            fail += 1
            continue
        try:
            analysis = await analyze_with_retry(article_data)
        except Exception as exc:
            print(f"  id={aid} analyze_fail: {str(exc)[:120]}", flush=True)
            fail += 1
            continue

        def _save() -> None:
            with SessionLocal() as session:
                an = session.scalar(
                    select(AnalysisModel).where(AnalysisModel.article_id == aid)
                )
                if an is None:
                    return
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

        await asyncio.to_thread(_save)
        print(f"  id={aid} OK  per={analysis.peronism_antiperonism.score:+.1f}  lib={analysis.statism_liberalism.score:+.1f}", flush=True)
        ok += 1

    elapsed = time.time() - t0
    print(f"\nOK={ok}  FAIL={fail}  tiempo={elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
