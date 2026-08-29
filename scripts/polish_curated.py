#!/usr/bin/env python3
"""Batch-generate LLM narratives for curated POIs (requires LIFETRIP_LLM_API_KEY)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

os.environ.setdefault("LIFETRIP_LLM_POLISH", "1")

from app.contracts import Stop  # noqa: E402
from app.narrative.polish import _call_llm, _save_llm_cache  # noqa: E402
from app.paths import CURATED, NARRATIVES  # noqa: E402


def main() -> int:
    if not os.getenv("LIFETRIP_LLM_API_KEY"):
        print("Set LIFETRIP_LLM_API_KEY and LIFETRIP_LLM_POLISH=1")
        return 1
    NARRATIVES.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(CURATED.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        vibe = data.get("vibe", "coffee")
        district = data.get("districtId", "")
        for s in data.get("stops") or []:
            stop = Stop(
                id=s["id"],
                code="XX-01",
                name=s["name"],
                district=district,
                lat=s["lat"],
                lng=s["lng"],
                tags=s.get("tags") or [],
                headline=s.get("headline") or "",
                body=s.get("body") or "",
                tip=s.get("tip") or "",
                sourceLabel=s.get("sourceLabel", "green"),
            )
            narr = _call_llm(stop=stop, vibe=vibe, district=district, index=0, total=1)
            if narr:
                safe = s["id"].replace("/", "_")
                out = NARRATIVES / f"{safe}.json"
                out.write_text(
                    json.dumps({**narr, "poiId": s["id"], "source": "llm"}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                _save_llm_cache(s["id"], vibe, narr)
                count += 1
                print("ok", s["id"])
    print(f"polished {count} stops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
