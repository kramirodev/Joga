"""Testes da validação de argumentos da CLI de revisão (sem banco)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from scripts import review_match_result as cli


def _settings(operators: set[str]) -> SimpleNamespace:
    return SimpleNamespace(review_operator_ids=frozenset(operators))


def test_unauthorized_operator_exits_with_3(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: _settings({"op-1"}))

    code = cli.main(
        [
            "--match-id",
            str(uuid.uuid4()),
            "--operator",
            "intruso",
            "--reason",
            "tentativa",
            "--decision",
            "VOID",
        ]
    )
    assert code == cli.EXIT_UNAUTHORIZED_OPERATOR


def test_finalize_requires_outcome(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: _settings({"op-1"}))

    code = cli.main(
        [
            "--match-id",
            str(uuid.uuid4()),
            "--operator",
            "op-1",
            "--reason",
            "decisão",
            "--decision",
            "FINALIZE",
        ]
    )
    assert code == cli.EXIT_INVALID_ARGUMENT


def test_outcome_is_rejected_for_void(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: _settings({"op-1"}))

    code = cli.main(
        [
            "--match-id",
            str(uuid.uuid4()),
            "--operator",
            "op-1",
            "--reason",
            "decisão",
            "--decision",
            "VOID",
            "--outcome",
            "TEAM_1",
        ]
    )
    assert code == cli.EXIT_INVALID_ARGUMENT


def test_reason_cannot_be_empty(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: _settings({"op-1"}))

    code = cli.main(
        [
            "--match-id",
            str(uuid.uuid4()),
            "--operator",
            "op-1",
            "--reason",
            "   ",
            "--decision",
            "VOID",
        ]
    )
    assert code == cli.EXIT_INVALID_ARGUMENT
