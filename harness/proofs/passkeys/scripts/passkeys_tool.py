#!/usr/bin/env python3
"""Ferramentas da prova de associação de passkeys (Android Digital Asset Links).

Subcomandos:
  statement    gera o assetlinks.json a partir de package + SHA-256
  fingerprint  extrai o SHA-256 do certificado de um APK assinado
  verify       valida um assetlinks.json publicado e consulta a API do Google

Uso típico:
  python passkeys_tool.py fingerprint --apk app-debug.apk
  python passkeys_tool.py statement --package com.anonymous.joga --fingerprint AA:BB:...
  python passkeys_tool.py verify --origin https://exemplo.vercel.app --package com.anonymous.joga
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RELATION = "delegate_permission/common.get_login_creds"
APP_LINKS_RELATION = "delegate_permission/common.handle_all_urls"
DEFAULT_OUT = (
    Path(__file__).resolve().parent.parent / "site" / ".well-known" / "assetlinks.json"
)
SHA256_HEX = re.compile(r"SHA-256 digest:\s*([0-9a-fA-F]{64})")
HEX_ONLY = re.compile(r"[^0-9A-Fa-f]")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Impede seguir redirecionamentos: o Android exige resposta 200 direta."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def normalize_fingerprint(value: str) -> str:
    """Aceita SHA-256 com ou sem ':' e devolve o formato do assetlinks."""
    hexdigits = HEX_ONLY.sub("", value)
    if len(hexdigits) != 64:
        raise ValueError("SHA-256 deve ter 64 dígitos hexadecimais")
    return ":".join(hexdigits[index : index + 2].upper() for index in range(0, 64, 2))


def build_statement(
    package: str,
    fingerprints: list[str],
    include_app_links: bool = False,
) -> list[dict[str, object]]:
    if not package or " " in package:
        raise ValueError("package_name inválido")
    if not fingerprints:
        raise ValueError("informe ao menos uma impressão SHA-256")
    relations = [RELATION]
    if include_app_links:
        relations.append(APP_LINKS_RELATION)
    return [
        {
            "relation": relations,
            "target": {
                "namespace": "android_app",
                "package_name": package,
                "sha256_cert_fingerprints": [
                    normalize_fingerprint(item) for item in fingerprints
                ],
            },
        }
    ]


def write_assetlinks(
    package: str,
    fingerprints: list[str],
    destination: Path = DEFAULT_OUT,
    include_app_links: bool = False,
) -> Path:
    statement = build_statement(package, fingerprints, include_app_links)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(statement, indent=2) + "\n", encoding="utf-8")
    return destination


def fingerprint_from_apk(apk: Path, apksigner: str) -> str:
    result = subprocess.run(
        [apksigner, "verify", "--print-certs", str(apk)],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    match = SHA256_HEX.search(output)
    if not match:
        raise RuntimeError(
            "não foi possível ler o SHA-256 do APK; confira o caminho do apksigner"
        )
    return normalize_fingerprint(match.group(1))


def verify(
    origin: str,
    package: str,
    expected_fingerprint: str | None = None,
    check_google: bool = True,
) -> list[str]:
    """Retorna a lista de problemas encontrados; vazia significa associação válida."""
    problems: list[str] = []
    url = origin.rstrip("/") + "/.well-known/assetlinks.json"
    opener = urllib.request.build_opener(NoRedirect())

    try:
        with opener.open(url, timeout=15) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400:
            return [f"a URL respondeu {error.code} (redirecionamento não é aceito)"]
        return [f"a URL respondeu HTTP {error.code}"]
    except urllib.error.URLError as error:
        return [f"falha de conexão: {error.reason}"]

    if status != 200:
        problems.append(f"status esperado 200, recebido {status}")
    if not content_type.lower().startswith("application/json"):
        problems.append(
            f"Content-Type esperado application/json, recebido {content_type!r}"
        )

    try:
        statements = json.loads(body)
    except json.JSONDecodeError:
        return problems + ["corpo não é JSON válido"]

    if not isinstance(statements, list):
        return problems + ["assetlinks.json deve ser uma lista"]

    expected = (
        normalize_fingerprint(expected_fingerprint) if expected_fingerprint else None
    )
    matching = []
    for statement in statements:
        target = statement.get("target", {}) if isinstance(statement, dict) else {}
        relations = statement.get("relation", []) if isinstance(statement, dict) else []
        if (
            RELATION in relations
            and target.get("namespace") == "android_app"
            and target.get("package_name") == package
        ):
            matching.append(target)

    if not matching:
        problems.append(f"nenhuma declaração para {package} com a relação {RELATION}")
    elif expected and not any(
        expected in target.get("sha256_cert_fingerprints", []) for target in matching
    ):
        problems.append(f"a impressão {expected} não está declarada para {package}")

    if check_google:
        query = urllib.parse.urlencode(
            {"source.web.site": origin.rstrip("/"), "relation": RELATION}
        )
        api = f"https://digitalassetlinks.googleapis.com/v1/statements:list?{query}"
        try:
            with urllib.request.urlopen(api, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            problems.append(f"consulta à API do Google falhou: {error}")
        else:
            google_statements = payload.get("statements", [])
            packages = [
                item.get("target", {}).get("androidApp", {}).get("packageName")
                for item in google_statements
            ]
            if package not in packages:
                problems.append(
                    f"a API do Google não reconheceu {package} para {origin}"
                )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    statement = subparsers.add_parser("statement", help="gera o assetlinks.json")
    statement.add_argument("--package", required=True)
    statement.add_argument("--fingerprint", action="append", required=True)
    statement.add_argument(
        "--app-links-relation",
        action="store_true",
        help=(
            "inclui delegate_permission/common.handle_all_urls junto da relação de "
            "credenciais; algumas versões do Google Password Manager só validam o RP ID "
            "com as duas relações"
        ),
    )
    statement.add_argument("--out", type=Path, default=DEFAULT_OUT)

    fingerprint = subparsers.add_parser("fingerprint", help="lê o SHA-256 de um APK")
    fingerprint.add_argument("--apk", type=Path, required=True)
    fingerprint.add_argument("--apksigner", required=True)

    verify_parser = subparsers.add_parser("verify", help="valida o arquivo publicado")
    verify_parser.add_argument("--origin", required=True)
    verify_parser.add_argument("--package", required=True)
    verify_parser.add_argument("--fingerprint")
    verify_parser.add_argument("--skip-google", action="store_true")

    args = parser.parse_args()

    if args.command == "statement":
        destination = write_assetlinks(
            args.package,
            args.fingerprint,
            args.out,
            include_app_links=args.app_links_relation,
        )
        print(f"assetlinks.json escrito em {destination}")
        return 0

    if args.command == "fingerprint":
        print(fingerprint_from_apk(args.apk, args.apksigner))
        return 0

    problems = verify(
        args.origin,
        args.package,
        expected_fingerprint=args.fingerprint,
        check_google=not args.skip_google,
    )
    if problems:
        print("FALHOU:")
        for problem in problems:
            print(f" - {problem}")
        return 1
    print(f"OK: {args.package} associado a {args.origin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
