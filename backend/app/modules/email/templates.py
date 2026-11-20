"""Templates transacionais em PT-BR (texto + HTML simples, sem rastreamento).

Regras fixas (ADR 0050):
- assunto e remetente determinados apenas pelo tipo;
- nenhum link mágico, imagem externa, pixel ou redirect;
- nenhum telefone, CPF, endereço, localização ou dado de pagamento;
- somente nome de exibição, código, validade e data/hora genérica.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from app.core.text import CONTROL_PATTERN
from app.modules.email.models import EMAIL_KINDS

CODE_PATTERN = re.compile(r"^\d{6}$")

SUBJECTS = {
    "email_verification": "Seu código de verificação do JOGA",
    "email_login": "Seu código de acesso do JOGA",
    "email_change_confirm": "Confirme seu novo e-mail no JOGA",
    "email_change_notice": "Seu e-mail de acesso ao JOGA foi alterado",
    "welcome": "Boas-vindas ao JOGA",
    "security_alert": "Alerta de segurança do JOGA",
    "account_deletion_notice": "Sobre a exclusão da sua conta JOGA",
    "password_reset": "Código para redefinir sua senha do JOGA",
    "password_changed": "Sua senha do JOGA foi alterada",
}

FOOTER = (
    "JOGA — plataforma de esportes.\n"
    "Este é um e-mail automático. Se precisar de ajuda, responda a esta mensagem."
)


class InvalidTemplate(ValueError):
    """Tipo de e-mail ou contexto de template inválido."""


@dataclass(frozen=True)
class RenderedTemplate:
    subject: str
    text: str
    html: str


def _safe_label(value: str | None, *, fallback: str = "") -> str:
    if not value:
        return fallback
    cleaned = CONTROL_PATTERN.sub(" ", value).strip()
    return cleaned[:60] or fallback


def _code_block(code: str, ttl_minutes: int) -> tuple[str, str]:
    if not CODE_PATTERN.fullmatch(code):
        raise InvalidTemplate("código inválido")
    if ttl_minutes <= 0 or ttl_minutes > 60:
        raise InvalidTemplate("validade inválida")
    text = (
        f"Seu código é {code}.\n"
        f"Ele é de uso único e expira em {ttl_minutes} minutos.\n"
        "Se você não solicitou este código, ignore esta mensagem."
    )
    html_body = (
        f"<p>Seu código é <strong>{code}</strong>.</p>"
        f"<p>Ele é de uso único e expira em {ttl_minutes} minutos.</p>"
        "<p>Se você não solicitou este código, ignore esta mensagem.</p>"
    )
    return text, html_body


def render(
    kind: str,
    *,
    code: str | None = None,
    ttl_minutes: int = 10,
    display_name: str | None = None,
    occurred_at: str | None = None,
    device_label: str | None = None,
    deletion_label: str | None = None,
) -> RenderedTemplate:
    """Renderiza um dos sete tipos transacionais permitidos."""
    if kind not in EMAIL_KINDS:
        raise InvalidTemplate("tipo de e-mail desconhecido")

    subject = SUBJECTS[kind]
    if kind in {
        "email_verification",
        "email_login",
        "email_change_confirm",
        "password_reset",
    }:
        if code is None:
            raise InvalidTemplate("código ausente")
        text_body, html_body = _code_block(code, ttl_minutes)
    elif kind == "password_changed":
        moment = _safe_label(occurred_at, fallback="data não informada")
        text_body = (
            f"A senha da sua conta JOGA foi alterada em {moment}.\n"
            "Se não foi você, use a opção de redefinir senha e procure o suporte "
            "pelo canal de resposta deste e-mail."
        )
        html_body = (
            f"<p>A senha da sua conta JOGA foi alterada em {html.escape(moment)}.</p>"
            "<p>Se não foi você, use a opção de redefinir senha e procure o suporte "
            "pelo canal de resposta deste e-mail.</p>"
        )
    elif kind == "email_change_notice":
        moment = _safe_label(occurred_at, fallback="data não informada")
        text_body = (
            "O e-mail de acesso da sua conta JOGA foi alterado "
            f"em {moment}.\n"
            "O endereço anterior não autentica mais.\n"
            "Se não foi você, procure o suporte imediatamente pelo canal de "
            "resposta deste e-mail."
        )
        html_body = (
            f"<p>O e-mail de acesso da sua conta JOGA foi alterado em {html.escape(moment)}.</p>"
            "<p>O endereço anterior não autentica mais.</p>"
            "<p>Se não foi você, procure o suporte imediatamente pelo canal de "
            "resposta deste e-mail.</p>"
        )
    elif kind == "welcome":
        name = _safe_label(display_name, fallback="jogador")
        text_body = (
            f"Olá, {name}.\n"
            "Sua conta JOGA foi criada e o e-mail está verificado.\n"
            "Você já pode registrar uma passkey nos ajustes de segurança para "
            "entrar sem depender de código."
        )
        escaped = html.escape(name)
        html_body = (
            f"<p>Olá, {escaped}.</p>"
            "<p>Sua conta JOGA foi criada e o e-mail está verificado.</p>"
            "<p>Você já pode registrar uma passkey nos ajustes de segurança para "
            "entrar sem depender de código.</p>"
        )
    elif kind == "security_alert":
        moment = _safe_label(occurred_at, fallback="data não informada")
        device = _safe_label(device_label, fallback="dispositivo não identificado")
        text_body = (
            f"Detectamos uma atividade de segurança na sua conta em {moment}.\n"
            f"Origem informada: {device}.\n"
            "Se não foi você, altere suas credenciais e procure o suporte pelo "
            "canal de resposta deste e-mail."
        )
        html_body = (
            f"<p>Detectamos uma atividade de segurança na sua conta em "
            f"{html.escape(moment)}.</p>"
            f"<p>Origem informada: {html.escape(device)}.</p>"
            "<p>Se não foi você, altere suas credenciais e procure o suporte pelo "
            "canal de resposta deste e-mail.</p>"
        )
    elif kind == "account_deletion_notice":
        moment = _safe_label(occurred_at, fallback="data não informada")
        stage = _safe_label(deletion_label, fallback="solicitada")
        text_body = (
            f"A exclusão da sua conta JOGA foi {stage} em {moment}.\n"
            "Se você não reconhece esta solicitação, procure o suporte pelo canal "
            "de resposta deste e-mail."
        )
        html_body = (
            f"<p>A exclusão da sua conta JOGA foi {html.escape(stage)} em "
            f"{html.escape(moment)}.</p>"
            "<p>Se você não reconhece esta solicitação, procure o suporte pelo canal "
            "de resposta deste e-mail.</p>"
        )
    else:  # pragma: no cover - EMAIL_KINDS cobre todos os casos acima
        raise InvalidTemplate("tipo de e-mail desconhecido")

    text = f"{text_body}\n\n{FOOTER}\n"
    body_html = f"{html_body}<p>{html.escape(FOOTER).replace(chr(10), '<br>')}</p>"
    document = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{html.escape(subject)}</title></head>"
        f"<body>{body_html}</body></html>"
    )
    # Nenhum template pode introduzir recurso externo ou link de clique.
    if "http://" in text or "https://" in text or "<img" in document or "<a " in document:
        raise InvalidTemplate("template não pode conter links ou imagens")
    return RenderedTemplate(subject=subject, text=text, html=document)


__all__ = ["InvalidTemplate", "RenderedTemplate", "SUBJECTS", "render"]
