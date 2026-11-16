"""Testes de propriedade de taxa e rateio (ADR 0049 §9.10)."""

from __future__ import annotations

import random

import pytest

from app.modules.payments.money import allocate_cents, compute_fee_cents


def test_allocate_cents_sums_exactly_and_stays_balanced() -> None:
    rng = random.Random(42)
    totals = [0, 1, 2, 3, 4, 5, 9, 10, 11, 99, 100, 101, 999, 1000, 12345, 100000]
    for parts in range(1, 31):
        for total in totals:
            shares = allocate_cents(total, parts)
            assert len(shares) == parts
            assert sum(shares) == total
            assert all(share >= 0 for share in shares)
            assert max(shares) - min(shares) <= 1
            if total >= parts:
                assert all(share > 0 for share in shares)
        total = rng.randint(0, 100000)
        shares = allocate_cents(total, parts)
        assert sum(shares) == total
        assert max(shares) - min(shares) <= 1


def test_allocate_cents_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        allocate_cents(-1, 2)
    with pytest.raises(ValueError):
        allocate_cents(10, 0)


def test_compute_fee_rounds_half_up() -> None:
    assert compute_fee_cents(5, 1000, 0) == 1
    assert compute_fee_cents(4, 1000, 0) == 0
    assert compute_fee_cents(15000, 2000, 800) == 3000
    assert compute_fee_cents(12000, 2000, 800) == 2400


def test_compute_fee_applies_floor_and_ceiling() -> None:
    assert compute_fee_cents(3000, 2000, 800) == 800
    assert compute_fee_cents(100, 2000, 800) == 100
    assert compute_fee_cents(10000, 0, 0) == 0
    assert compute_fee_cents(10000, 10000, 0) == 10000


@pytest.mark.parametrize(
    ("price", "percent", "minimum"),
    [
        (-1, 2000, 0),
        (100, -1, 0),
        (100, 10001, 0),
        (100, 2000, -1),
    ],
)
def test_compute_fee_rejects_invalid_input(price: int, percent: int, minimum: int) -> None:
    with pytest.raises(ValueError):
        compute_fee_cents(price, percent, minimum)
