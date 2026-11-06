"""Executa uma simulação sintética do motor de rating.

Uso:
    python -m scripts.simulate_ratings
    python -m scripts.simulate_ratings --players 80 --matches 5000 --seed 42
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from app.modules.ratings.simulation import simulate_ladder


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--players", type=int, default=60)
    parser.add_argument("--matches", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    try:
        result = simulate_ladder(
            players=args.players,
            matches=args.matches,
            seed=args.seed,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(
        f"jogadores={result.players} partidas={result.matches} "
        f"media={result.average_rating:.2f} "
        f"quartil_inferior={result.low_quartile_rating:.2f} "
        f"quartil_superior={result.high_quartile_rating:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
