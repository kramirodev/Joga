"""Executa uma carga HTTP local simples e reporta latência/erros.

Uso:
    python -m scripts.load_test --requests 200 --concurrency 20
    python -m scripts.load_test --path /api/v1/sports --requests 100
    python -m scripts.load_test --token <access_token> --path /api/v1/matches
"""

from __future__ import annotations

import argparse
import asyncio
import math
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class LoadResult:
    requests: int
    concurrency: int
    successes: int
    failures: int
    status_codes: dict[int, int]
    p50_ms: float
    p95_ms: float
    p99_ms: float
    duration_seconds: float


async def _run(
    *,
    base_url: str,
    path: str,
    requests: int,
    concurrency: int,
    token: str | None,
) -> LoadResult:
    semaphore = asyncio.Semaphore(concurrency)
    statuses: Counter[int] = Counter()
    latencies: list[float] = []
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    started = time.perf_counter()

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:

        async def one() -> None:
            async with semaphore:
                moment = time.perf_counter()
                try:
                    response = await client.get(path, headers=headers)
                    latencies.append((time.perf_counter() - moment) * 1000)
                    statuses[response.status_code] += 1
                except Exception:
                    return

        await asyncio.gather(*(one() for _ in range(requests)))

    duration = time.perf_counter() - started
    ordered = sorted(latencies)

    def percentile(value: float) -> float:
        if not ordered:
            return 0.0
        index = min(len(ordered) - 1, max(0, math.ceil(value * len(ordered)) - 1))
        return ordered[index]

    successes = sum(count for code, count in statuses.items() if 200 <= code < 400)
    failures = requests - successes
    return LoadResult(
        requests=requests,
        concurrency=concurrency,
        successes=successes,
        failures=failures,
        status_codes=dict(sorted(statuses.items())),
        p50_ms=percentile(0.50),
        p95_ms=percentile(0.95),
        p99_ms=percentile(0.99),
        duration_seconds=duration,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/api/v1/health/live")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--token")
    args = parser.parse_args(argv)
    if args.requests <= 0 or args.concurrency <= 0:
        parser.error("--requests e --concurrency devem ser positivos")

    result = asyncio.run(
        _run(
            base_url=args.base_url,
            path=args.path,
            requests=args.requests,
            concurrency=args.concurrency,
            token=args.token,
        )
    )
    print(
        f"requests={result.requests} concurrency={result.concurrency} "
        f"successes={result.successes} failures={result.failures} "
        f"status={result.status_codes} "
        f"p50_ms={result.p50_ms:.1f} p95_ms={result.p95_ms:.1f} "
        f"p99_ms={result.p99_ms:.1f} duration_s={result.duration_seconds:.2f}"
    )
    return 0 if result.failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
