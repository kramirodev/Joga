"""Constantes de teste para CPF/termos; nenhuma chave real."""

from __future__ import annotations

import base64

from pydantic import SecretStr

TEST_CPF_KEY = base64.b64encode(b"j" * 32).decode("ascii")
TEST_CPF_KEY_ID = "test-v1"
TEST_CPF = "52998224725"


def cpf_key_kwargs() -> dict[str, object]:
    return {
        "cpf_key": SecretStr(TEST_CPF_KEY),
        "cpf_key_id": TEST_CPF_KEY_ID,
    }
