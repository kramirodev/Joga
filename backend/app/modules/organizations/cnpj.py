"""Consulta e validação de CNPJ para cadastro de organizações (ADR 0062).

A consulta usa a BrasilAPI ``/cnpj/v1``. Testes injetam ``fetch_json`` e nunca
tocam a rede. O resultado é reduzido a um snapshot mascarado: o CPF dos sócios
aparece apenas como máscara fornecida pela Receita (por exemplo
``***682847**``), nunca em claro.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

CNPJ_DIGITS = re.compile(r"\D")

SITUACAO_ATIVA = "ATIVA"

# CNAEs aceitos como atividade esportiva. A lista é intencionalmente fechada e
# privilegia operação de instalações, clubes e ensino de esportes. A descrição
# fica ao lado para auditoria e para a mensagem devolvida ao painel.
COMPATIBLE_CNAES: dict[str, str] = {
    "8591100": "Ensino de esportes",
    "9311500": "Gestão de instalações de esportes",
    "9312300": "Clubes sociais, esportivos e similares",
    "9313100": "Atividades de condicionamento físico",
    "9319101": "Produção e promoção de eventos esportivos",
    "9319199": "Outras atividades esportivas não especificadas anteriormente",
    "9329899": "Outras atividades de recreação e lazer não especificadas anteriormente",
}


class CnpjError(Exception):
    """Erro base de CNPJ; mensagens nunca incluem o documento recebido."""


class InvalidCnpj(CnpjError):
    """CNPJ fora do formato ou com dígitos verificadores inválidos."""


class CnpjNotFound(CnpjError):
    """CNPJ não encontrado na base consultada."""


class CnpjProviderUnavailable(CnpjError):
    """Provedor de CNPJ indisponível, lento ou com resposta inválida."""


@dataclass(frozen=True)
class QsaPartner:
    """Sócio conforme o QSA, com CPF já mascarado pela fonte."""

    nome: str
    cpf_masked: str | None
    qualificacao: str | None


@dataclass(frozen=True)
class CnpjRecord:
    """Dados mínimos e não sensíveis de um CNPJ consultado."""

    cnpj: str
    razao_social: str
    situacao_cadastral: str
    cnae_fiscal: str
    nome_fantasia: str | None = None
    data_situacao_cadastral: str | None = None
    cnae_descricao: str | None = None
    secondary_cnaes: tuple[tuple[str, str | None], ...] = ()
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    bairro: str | None = None
    complemento: str | None = None
    qsa: tuple[QsaPartner, ...] = ()

    def all_cnaes(self) -> tuple[str, ...]:
        return (self.cnae_fiscal, *(code for code, _description in self.secondary_cnaes))

    def compatible_cnae(self) -> str | None:
        """Primeiro CNAE compatível, priorizando a atividade principal."""
        for code in self.all_cnaes():
            if code in COMPATIBLE_CNAES:
                return code
        return None

    def snapshot(self) -> dict[str, Any]:
        """Versão persistível/auditável, sem CPF de sócio em claro."""
        return {
            "razao_social": self.razao_social,
            "nome_fantasia": self.nome_fantasia,
            "situacao_cadastral": self.situacao_cadastral,
            "data_situacao_cadastral": self.data_situacao_cadastral,
            "cnae_fiscal": self.cnae_fiscal,
            "cnae_fiscal_descricao": self.cnae_descricao,
            "cnaes_secundarios": [
                {"codigo": code, "descricao": description}
                for code, description in self.secondary_cnaes
            ],
            "municipio": self.municipio,
            "uf": self.uf,
            "cep": self.cep,
            "logradouro": self.logradouro,
            "numero": self.numero,
            "bairro": self.bairro,
            "complemento": self.complemento,
            "qsa": [
                {
                    "nome": partner.nome,
                    "cpf_masked": partner.cpf_masked,
                    "qualificacao": partner.qualificacao,
                }
                for partner in self.qsa
            ],
        }


class CnpjLookup(Protocol):
    """Contrato de consulta; permite mock HTTP nos testes."""

    def lookup(self, cnpj: str) -> CnpjRecord: ...


def normalize_cnpj(value: str) -> str:
    """Valida 14 dígitos e os verificadores, devolvendo apenas números."""
    digits = CNPJ_DIGITS.sub("", value or "")
    if len(digits) != 14 or len(set(digits)) == 1:
        raise InvalidCnpj("CNPJ deve ter 14 dígitos")
    weights_first = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    weights_second = (6, *weights_first)
    for weights, position in ((weights_first, 12), (weights_second, 13)):
        total = sum(
            int(digit) * weight for digit, weight in zip(digits[:position], weights, strict=True)
        )
        remainder = total % 11
        expected = 0 if remainder < 2 else 11 - remainder
        if int(digits[position]) != expected:
            raise InvalidCnpj("CNPJ inválido")
    return digits


def mask_cnpj(cnpj: str) -> str:
    """Máscara para auditoria; não revela filial nem ordem."""
    digits = CNPJ_DIGITS.sub("", cnpj)
    if len(digits) != 14:
        return "***"
    return f"{digits[:2]}.***.***/****-{digits[-2:]}"


def mask_cpf(last2: str | None) -> str | None:
    if last2 is None or len(last2) != 2 or not last2.isdigit():
        return None
    return f"***.***.***-{last2}"


def normalize_name(value: str | None) -> str:
    """Maiúsculas sem acento, pontuação ou espaços duplicados."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    alphanumeric = re.sub(r"[^A-Za-z0-9]+", " ", without_accents)
    return " ".join(alphanumeric.upper().split())


def names_match(profile_name: str | None, partner_name: str | None) -> bool:
    """Compara nomes tolerando abreviações razoáveis do perfil.

    O nome completo do sócio sempre precisa conter os tokens informados. Um
    único token é rejeitado para não aprovar homônimos por primeiro nome.
    """
    profile = normalize_name(profile_name)
    partner = normalize_name(partner_name)
    if not profile or not partner:
        return False
    if profile == partner:
        return True
    profile_tokens = profile.split()
    partner_tokens = set(partner.split())
    return len(profile_tokens) >= 2 and all(token in partner_tokens for token in profile_tokens)


def cpf_masked_matches(masked: str | None, cpf: str) -> bool:
    """Compara o CPF com a máscara da Receita sem decifrar o valor do sócio.

    A BrasilAPI entrega ``***123456**`` (dígitos 4 a 9 do CPF). Aceitamos também
    CPF completo e a máscara ``***.***.***-12``; a comparação por dois dígitos
    só é aceita porque o nome do sócio também precisa coincidir.
    """
    if not masked:
        return False
    digits = CNPJ_DIGITS.sub("", masked)
    if len(digits) == 11:
        return digits == cpf
    if len(digits) == 6:
        return digits == cpf[3:9]
    if len(digits) == 2:
        return digits == cpf[-2:]
    return False


def normalize_postal_code(value: str | None) -> str | None:
    if value is None:
        return None
    digits = CNPJ_DIGITS.sub("", value)
    return digits if len(digits) == 8 else None


def address_matches(
    snapshot: dict[str, Any] | None,
    *,
    city: str | None,
    state: str | None,
    postal_code: str | None,
) -> bool:
    """Confere município/UF e, na falta de município, o prefixo do CEP.

    O provedor não devolve coordenadas; o CEP de cinco dígitos funciona como o
    "raio" determinístico disponível sem uma segunda consulta externa.
    """
    if not snapshot:
        return False
    snapshot_city = normalize_name(str(snapshot.get("municipio") or ""))
    snapshot_state = str(snapshot.get("uf") or "").strip().upper()
    snapshot_cep = normalize_postal_code(str(snapshot.get("cep") or ""))
    normalized_state = (state or "").strip().upper()
    normalized_cep = normalize_postal_code(postal_code)

    if normalized_state and snapshot_state and normalized_state != snapshot_state:
        return False
    if city:
        return bool(snapshot_city) and normalize_name(city) == snapshot_city
    if normalized_cep:
        if snapshot_cep is None:
            return False
        return normalized_cep[:5] == snapshot_cep[:5]
    return False


FetchJson = Callable[[str, float], dict[str, object]]


class BrasilApiCnpjLookup:
    """Consulta BrasilAPI com timeout curto, retry limitado e cache curto."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 5.0,
        attempts: int = 2,
        cache_ttl_seconds: int = 300,
        fetch_json: FetchJson | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._attempts = max(1, attempts)
        self._cache_ttl = timedelta(seconds=max(0, cache_ttl_seconds))
        self._fetch_json = fetch_json or _urlopen_json
        self._cache: dict[str, tuple[datetime, CnpjRecord]] = {}

    def lookup(self, cnpj: str) -> CnpjRecord:
        normalized = normalize_cnpj(cnpj)
        cached = self._cache.get(normalized)
        now = datetime.now(UTC)
        if cached is not None and cached[0] > now:
            return cached[1]

        last_error: Exception | None = None
        for _attempt in range(self._attempts):
            url = f"{self._base_url}/{normalized}"
            try:
                payload = self._fetch_json(url, self._timeout)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise CnpjNotFound("CNPJ não encontrado") from error
                last_error = error
                continue
            except TimeoutError as error:
                last_error = error
                continue
            except (urllib.error.URLError, json.JSONDecodeError, ValueError) as error:
                last_error = error
                continue

            record = _parse_payload(payload, normalized)
            if self._cache_ttl.total_seconds() > 0:
                self._cache[normalized] = (now + self._cache_ttl, record)
            return record

        raise CnpjProviderUnavailable("provedor de CNPJ indisponível") from last_error


REQUEST_HEADERS = {
    # A BrasilAPI atrás do Cloudflare responde 403 ao User-Agent padrão do urllib.
    "User-Agent": "JOGA/0.1 (local; contato: dev@joga.invalid)",
    "Accept": "application/json",
}


def _urlopen_json(url: str, timeout: float) -> dict[str, object]:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise CnpjProviderUnavailable("resposta de CNPJ inválida")
    return {str(key): value for key, value in parsed.items()}


def _parse_payload(payload: dict[str, object], cnpj: str) -> CnpjRecord:
    returned_cnpj = payload.get("cnpj")
    if isinstance(returned_cnpj, str):
        if CNPJ_DIGITS.sub("", returned_cnpj) != cnpj:
            raise CnpjProviderUnavailable("resposta de CNPJ para outro documento")
    razao_social = payload.get("razao_social")
    situacao = payload.get("descricao_situacao_cadastral") or payload.get("situacao_cadastral")
    cnae = payload.get("cnae_fiscal")
    if not isinstance(razao_social, str) or not razao_social.strip():
        raise CnpjProviderUnavailable("resposta de CNPJ sem razão social")
    if not isinstance(situacao, str) or not situacao.strip():
        raise CnpjProviderUnavailable("resposta de CNPJ sem situação cadastral")
    cnae_code = _cnae_code(cnae)
    if cnae_code is None:
        raise CnpjProviderUnavailable("resposta de CNPJ sem CNAE principal")

    secondary: list[tuple[str, str | None]] = []
    raw_secondary = payload.get("cnaes_secundarios")
    if isinstance(raw_secondary, list):
        for item in raw_secondary:
            if not isinstance(item, dict):
                continue
            code = _cnae_code(item.get("codigo"))
            if code is None:
                continue
            description = item.get("descricao")
            secondary.append((code, description if isinstance(description, str) else None))

    partners: list[QsaPartner] = []
    raw_qsa = payload.get("qsa")
    if isinstance(raw_qsa, list):
        for item in raw_qsa:
            if not isinstance(item, dict):
                continue
            name = item.get("nome_socio") or item.get("nome")
            if not isinstance(name, str) or not name.strip():
                continue
            masked = item.get("cnpj_cpf_do_socio") or item.get("cpf_cnpj_socio")
            qualification = item.get("qualificacao_socio")
            partners.append(
                QsaPartner(
                    nome=" ".join(name.split()),
                    cpf_masked=masked if isinstance(masked, str) else None,
                    qualificacao=(
                        " ".join(qualification.split())
                        if isinstance(qualification, str) and qualification.strip()
                        else None
                    ),
                )
            )

    raw_cep = payload.get("cep")
    cep = normalize_postal_code(raw_cep if isinstance(raw_cep, str) else None)
    uf = payload.get("uf")
    return CnpjRecord(
        cnpj=cnpj,
        razao_social=" ".join(razao_social.split()),
        situacao_cadastral=" ".join(situacao.split()).upper(),
        cnae_fiscal=cnae_code,
        nome_fantasia=_optional_text(payload.get("nome_fantasia")),
        data_situacao_cadastral=_optional_text(payload.get("data_situacao_cadastral")),
        cnae_descricao=_optional_text(payload.get("cnae_fiscal_descricao")),
        secondary_cnaes=tuple(secondary),
        municipio=_optional_text(payload.get("municipio")),
        uf=uf.strip().upper()[:2] if isinstance(uf, str) and uf.strip() else None,
        cep=cep,
        logradouro=_optional_text(payload.get("logradouro")),
        numero=_optional_text(payload.get("numero")),
        bairro=_optional_text(payload.get("bairro")),
        complemento=_optional_text(payload.get("complemento")),
        qsa=tuple(partners),
    )


def _cnae_code(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return f"{value:07d}"
    if isinstance(value, str):
        digits = CNPJ_DIGITS.sub("", value)
        if len(digits) == 7:
            return digits
    return None


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split())
    return clean or None


__all__ = [
    "BrasilApiCnpjLookup",
    "COMPATIBLE_CNAES",
    "CnpjError",
    "CnpjLookup",
    "CnpjNotFound",
    "CnpjProviderUnavailable",
    "CnpjRecord",
    "InvalidCnpj",
    "QsaPartner",
    "SITUACAO_ATIVA",
    "address_matches",
    "cpf_masked_matches",
    "mask_cnpj",
    "mask_cpf",
    "names_match",
    "normalize_cnpj",
    "normalize_name",
    "normalize_postal_code",
]
