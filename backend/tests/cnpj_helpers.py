"""Fixtures compartilhadas da verificação de CNPJ (ADR 0062)."""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator
from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.organizations.cnpj import CnpjRecord, QsaPartner
from app.modules.organizations.dependency import get_cnpj_lookup
from app.modules.profile.cpf import encrypt_cpf, hash_cpf
from app.modules.profile.models import UserProfile
from tests.helpers_results import make_user

PARTNER_NAME = "ANA SOUZA"
PARTNER_CPF = "11144477735"
PARTNER_CPF_MASKED = "***444777**"
# Todos compartilham os dígitos 444777 do QSA e têm verificadores válidos; a
# unicidade por conta (ADR 0065) exige CPFs distintos para usuários distintos.
_PARTNER_CPF_ALTERNATIVES = (
    "00044477783",
    "00144477700",
    "00244477736",
    "00344477762",
    "00444477799",
    "00544477715",
    "00644477741",
    "00744477778",
    "00844477702",
    "00944477720",
    "01044477709",
    "01144477727",
)
_CPF_COUNTER = itertools.count()

# CNPJs com dígitos verificadores válidos, reservados para testes.
VALID_CNPJS = (
    "11222333000181",
    "22333444000181",
    "33444555000181",
    "44555666000181",
    "55666777000181",
    "66777888000181",
    "77888999000181",
    "88999000000198",
    "19131243000197",
    "12345678000195",
)
_CNPJ_COUNTER = itertools.count()


def next_test_cnpj() -> str:
    return VALID_CNPJS[next(_CNPJ_COUNTER) % len(VALID_CNPJS)]


def next_partner_cpf() -> str:
    """CPF válido distinto de ``PARTNER_CPF`` e compatível com a máscara do QSA."""
    index = next(_CPF_COUNTER) % len(_PARTNER_CPF_ALTERNATIVES)
    return _PARTNER_CPF_ALTERNATIVES[index]


def cnpj_record(**overrides: object) -> CnpjRecord:
    """CNPJ ativo, esportivo e sediado no Rio de Janeiro."""

    base = CnpjRecord(
        cnpj="11222333000181",
        razao_social="ARENA TESTE LTDA",
        nome_fantasia="Arena Teste",
        situacao_cadastral="ATIVA",
        data_situacao_cadastral="2020-01-01",
        cnae_fiscal="9311500",
        cnae_descricao="Gestão de instalações de esportes",
        secondary_cnaes=(("9319199", "Outras atividades esportivas"),),
        municipio="RIO DE JANEIRO",
        uf="RJ",
        cep="20541004",
        logradouro="AVENIDA PAULO DE FRONTIN",
        numero="100",
        bairro="MARACANA",
        complemento=None,
        qsa=(QsaPartner(nome=PARTNER_NAME, cpf_masked=PARTNER_CPF_MASKED, qualificacao="Sócia"),),
    )
    return replace(base, **overrides)


class FakeCnpjLookup:
    """Substitui a BrasilAPI sem tocar a rede."""

    def __init__(
        self,
        record: CnpjRecord | None = None,
        *,
        error: Exception | None = None,
        records: dict[str, CnpjRecord] | None = None,
    ) -> None:
        self.default = record or cnpj_record()
        self.error = error
        self.records = records or {}
        self.calls: list[str] = []

    def lookup(self, cnpj: str) -> CnpjRecord:
        self.calls.append(cnpj)
        if self.error is not None:
            raise self.error
        record = self.records.get(cnpj, self.default)
        return replace(record, cnpj=cnpj)


def attach_partner_profile(
    session: Session,
    user_id: uuid.UUID,
    *,
    display_name: str = PARTNER_NAME,
    cpf: str = PARTNER_CPF,
) -> None:
    ciphertext, key_id, last2 = encrypt_cpf(cpf, user_id, get_settings())
    profile = session.get(UserProfile, user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        session.add(profile)
    profile.display_name = display_name
    profile.cpf_ciphertext = ciphertext
    profile.cpf_key_id = key_id
    profile.cpf_last2 = last2
    profile.cpf_hash = hash_cpf(cpf, get_settings())
    session.flush()


def make_cnpj_user(
    session: Session,
    *,
    display_name: str = PARTNER_NAME,
    cpf: str = PARTNER_CPF,
) -> uuid.UUID:
    user_id = make_user(session)
    attach_partner_profile(session, user_id, display_name=display_name, cpf=cpf)
    return user_id


def api_with_lookup(
    client: TestClient,
    db_session: Session,
    lookup: FakeCnpjLookup,
) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_cnpj_lookup] = lambda: lookup
    return client


__all__ = [
    "FakeCnpjLookup",
    "PARTNER_CPF",
    "PARTNER_CPF_MASKED",
    "PARTNER_NAME",
    "VALID_CNPJS",
    "api_with_lookup",
    "attach_partner_profile",
    "cnpj_record",
    "make_cnpj_user",
    "next_partner_cpf",
    "next_test_cnpj",
]
