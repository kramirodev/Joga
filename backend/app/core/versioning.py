"""Comparação de versões semânticas numéricas usadas pelo gate do app."""

from __future__ import annotations

import re

SEMVER_PATTERN = re.compile(r"^(\d{1,5})\.(\d{1,5})\.(\d{1,5})$")
Version = tuple[int, int, int]


def parse_version(value: str | None) -> Version | None:
    """Converte ``MAJOR.MINOR.PATCH`` em tupla; rejeita pré-release e texto."""
    if not isinstance(value, str):
        return None
    match = SEMVER_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


__all__ = ["SEMVER_PATTERN", "Version", "parse_version"]
