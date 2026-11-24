"""Auditoria read-only da exposição do schema ``public`` do PostgreSQL.

Uso:
    python -m scripts.audit_db_security
    python -m scripts.audit_db_security --json

Lê ``JOGA_DATABASE_URL`` (ex.: ``postgresql+psycopg://...``). A URL nunca é
impressa e o script abre uma transação ``READ ONLY``; ele não altera nada.

O resumo não contém linhas de tabela nem dados pessoais. O código de saída é
diferente de zero quando encontra violação:

* tabela da aplicação sem RLS;
* ``USAGE`` do schema ``public`` para ``PUBLIC``, ``anon`` ou ``authenticated``;
* ``SELECT``/``INSERT``/``UPDATE``/``DELETE``/``TRUNCATE`` de ``anon`` ou
  ``authenticated`` em tabela da aplicação;
* ``USAGE``/``UPDATE``/``SELECT`` de ``anon`` ou ``authenticated`` em
  sequence da aplicação;
* ``EXECUTE`` de ``anon`` ou ``authenticated`` em função/procedure da
  aplicação;
* privilégios padrão em ``public`` para ``anon``/``authenticated`` em
  tabelas, sequences ou funções, ou ``PUBLIC`` em funções.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
SEQUENCE_PRIVILEGES = ("USAGE", "UPDATE", "SELECT")
ROUTINE_PRIVILEGES = ("EXECUTE",)
SCHEMA_ROLES = ("anon", "authenticated")
_REPORTED_ROLES = ("anon", "authenticated", "service_role", "postgres")
_CONNECTION_URL = re.compile(r"(?i)(?:postgres(?:ql)?(?:\+[a-z0-9_]+)?://)\S+")
_PASSWORD = re.compile(r"(?i)(password\s*=\s*)\S+")

# Relações do app em ``public``. Objetos instalados por extensões (PostGIS,
# pgcrypto etc.) são identificados pela dependência de extensão e ficam de
# fora; ``spatial_ref_sys`` e ``alembic_version`` também não são do app.
_APP_RELATIONS = """
    SELECT c.oid,
           c.relname,
           c.relkind,
           c.relrowsecurity,
           c.reloptions
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND c.relname NOT IN ('spatial_ref_sys', 'alembic_version')
       AND NOT EXISTS (
           SELECT 1
             FROM pg_depend d
            WHERE d.classid = 'pg_class'::regclass
              AND d.objid = c.oid
              AND d.deptype = 'e'
       )
"""

_APP_SEQUENCES = """
    SELECT c.oid, c.relname
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind = 'S'
       AND NOT EXISTS (
           SELECT 1
             FROM pg_depend d
            WHERE d.classid = 'pg_class'::regclass
              AND d.objid = c.oid
              AND d.deptype = 'e'
       )
"""

_APP_ROUTINES = """
    SELECT p.oid, p.proname
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.prokind IN ('f', 'p')
       AND pg_get_userbyid(p.proowner) = current_user
"""

_DEFAULT_PRIVILEGES = """
    SELECT CASE d.defaclobjtype
               WHEN 'r' THEN 'TABLES'
               WHEN 'S' THEN 'SEQUENCES'
               WHEN 'f' THEN 'FUNCTIONS'
               ELSE d.defaclobjtype::text
           END AS object_type,
           COALESCE(r.rolname, 'PUBLIC') AS grantee,
           acl.privilege_type
      FROM pg_default_acl d
      CROSS JOIN LATERAL aclexplode(d.defaclacl) AS acl
      LEFT JOIN pg_roles r ON r.oid = acl.grantee
     WHERE d.defaclnamespace = 'public'::regnamespace
       AND d.defaclrole = (SELECT oid FROM pg_roles WHERE rolname = current_user)
       AND (acl.grantee = 0 OR r.rolname IN ('anon', 'authenticated'))
     ORDER BY object_type, grantee, acl.privilege_type
"""


def _database_url() -> str:
    url = os.environ.get("JOGA_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("JOGA_DATABASE_URL não definido")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("JOGA_DATABASE_URL deve ser PostgreSQL (postgresql+psycopg)")
    return url


def _sanitize(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    message = _CONNECTION_URL.sub("<url-omitida>", message)
    message = _PASSWORD.sub(r"\1<omitido>", message)
    return message


def _present_roles(connection: Connection) -> list[str]:
    placeholders = ", ".join(f":role_{index}" for index in range(len(_REPORTED_ROLES)))
    params = {f"role_{index}": name for index, name in enumerate(_REPORTED_ROLES)}
    query = text(
        f"SELECT rolname FROM pg_roles "
        f"WHERE rolname IN ({placeholders}) OR rolname = current_user "
        f"ORDER BY rolname"
    )
    return [str(row[0]) for row in connection.execute(query, params)]


def _role_exists(connection: Connection, role: str) -> bool:
    return bool(
        connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar()
    )


def _public_schema_acl(connection: Connection) -> dict[str, Any]:
    rows = connection.execute(
        text(
            """
            SELECT acl.privilege_type AS privilege_type
              FROM pg_namespace AS n
              CROSS JOIN LATERAL aclexplode(
                  coalesce(n.nspacl, acldefault('n', n.nspowner))
              ) AS acl
             WHERE n.nspname = 'public'
               AND acl.grantee = 0
             ORDER BY acl.privilege_type
            """
        )
    )
    public_privileges = {str(row.privilege_type) for row in rows}

    result: dict[str, Any] = {
        "public": {
            "usage": "USAGE" in public_privileges,
            "create": "CREATE" in public_privileges,
        }
    }
    for role in SCHEMA_ROLES:
        if not _role_exists(connection, role):
            result[role] = {"present": False, "usage": False, "create": False}
            continue
        usage = connection.execute(
            text("SELECT has_schema_privilege(CAST(:role AS name), 'public', 'USAGE')"),
            {"role": role},
        ).scalar()
        create = connection.execute(
            text("SELECT has_schema_privilege(CAST(:role AS name), 'public', 'CREATE')"),
            {"role": role},
        ).scalar()
        result[role] = {
            "present": True,
            "usage": bool(usage),
            "create": bool(create),
        }
    return result


def _relation_privileges(connection: Connection, role: str) -> dict[str, Any]:
    if not _role_exists(connection, role):
        return {"present": False, "by_privilege": {p: 0 for p in PRIVILEGES}, "tables": []}

    rows = connection.execute(
        text(
            f"""
            SELECT rel.relname,
                   privilege.privilege
              FROM ({_APP_RELATIONS}) AS rel
             CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'),
                                ('DELETE'), ('TRUNCATE'))
                  AS privilege(privilege)
             WHERE has_table_privilege(
                       CAST(:role AS name),
                       rel.oid,
                       privilege.privilege
                   )
             ORDER BY rel.relname, privilege.privilege
            """
        ),
        {"role": role},
    )
    by_privilege = {privilege: 0 for privilege in PRIVILEGES}
    tables: set[str] = set()
    for row in rows:
        by_privilege[str(row.privilege)] += 1
        tables.add(str(row.relname))
    return {
        "present": True,
        "by_privilege": by_privilege,
        "tables": sorted(tables),
    }


def _sequence_privileges(connection: Connection, role: str) -> dict[str, Any]:
    if not _role_exists(connection, role):
        return {
            "present": False,
            "by_privilege": {p: 0 for p in SEQUENCE_PRIVILEGES},
            "sequences": [],
        }

    rows = connection.execute(
        text(
            f"""
            SELECT seq.relname,
                   privilege.privilege
              FROM ({_APP_SEQUENCES}) AS seq
             CROSS JOIN (VALUES ('USAGE'), ('UPDATE'), ('SELECT'))
                  AS privilege(privilege)
             WHERE has_sequence_privilege(
                       CAST(:role AS name),
                       seq.oid,
                       privilege.privilege
                   )
             ORDER BY seq.relname, privilege.privilege
            """
        ),
        {"role": role},
    )
    by_privilege = {privilege: 0 for privilege in SEQUENCE_PRIVILEGES}
    sequences: set[str] = set()
    for row in rows:
        by_privilege[str(row.privilege)] += 1
        sequences.add(str(row.relname))
    return {
        "present": True,
        "by_privilege": by_privilege,
        "sequences": sorted(sequences),
    }


def _routine_privileges(connection: Connection, role: str) -> dict[str, Any]:
    if not _role_exists(connection, role):
        return {
            "present": False,
            "by_privilege": {p: 0 for p in ROUTINE_PRIVILEGES},
            "routines": [],
        }

    rows = connection.execute(
        text(
            f"""
            SELECT routine.proname,
                   privilege.privilege
              FROM ({_APP_ROUTINES}) AS routine
             CROSS JOIN (VALUES ('EXECUTE')) AS privilege(privilege)
             WHERE has_function_privilege(
                       CAST(:role AS name),
                       routine.oid,
                       privilege.privilege
                   )
             ORDER BY routine.proname
            """
        ),
        {"role": role},
    )
    by_privilege = {privilege: 0 for privilege in ROUTINE_PRIVILEGES}
    routines: set[str] = set()
    for row in rows:
        by_privilege[str(row.privilege)] += 1
        routines.add(str(row.proname))
    return {
        "present": True,
        "by_privilege": by_privilege,
        "routines": sorted(routines),
    }


def _default_privilege_entries(connection: Connection) -> list[dict[str, str]]:
    rows = connection.execute(text(_DEFAULT_PRIVILEGES))
    return [
        {
            "object_type": str(row.object_type),
            "grantee": str(row.grantee),
            "privilege": str(row.privilege_type),
        }
        for row in rows
    ]


def audit(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))

        roles = _present_roles(connection)
        schema_acl = _public_schema_acl(connection)

        relations = list(
            connection.execute(text(f"SELECT * FROM ({_APP_RELATIONS}) AS rel ORDER BY relname"))
        )
        app_tables = [row for row in relations if row.relkind in ("r", "p")]
        views = [row for row in relations if row.relkind == "v"]
        missing_rls = sorted(str(row.relname) for row in app_tables if not row.relrowsecurity)
        no_security_invoker = sorted(
            str(row.relname)
            for row in views
            if "security_invoker=true" not in set(row.reloptions or ())
        )

        privileges = {role: _relation_privileges(connection, role) for role in SCHEMA_ROLES}
        sequences = list(
            connection.execute(text(f"SELECT * FROM ({_APP_SEQUENCES}) AS rel ORDER BY relname"))
        )
        routines_total = int(
            connection.scalar(text(f"SELECT count(*) FROM ({_APP_ROUTINES}) AS routine")) or 0
        )
        sequence_privileges = {
            role: _sequence_privileges(connection, role) for role in SCHEMA_ROLES
        }
        routine_privileges = {role: _routine_privileges(connection, role) for role in SCHEMA_ROLES}
        default_entries = _default_privilege_entries(connection)

        connection.rollback()

    violations: list[str] = []
    warnings: list[str] = []
    default_violations: list[str] = []

    if schema_acl["public"]["usage"]:
        violations.append("schema public: PUBLIC tem USAGE")
    for role in SCHEMA_ROLES:
        if schema_acl[role]["present"] and schema_acl[role]["usage"]:
            violations.append(f"schema public: {role} tem USAGE")

    for table in missing_rls:
        violations.append(f"tabela {table} sem RLS")

    for role in SCHEMA_ROLES:
        role_privileges = privileges[role]
        if not role_privileges["present"]:
            continue
        for privilege, count in role_privileges["by_privilege"].items():
            if count:
                violations.append(f"{role} tem {privilege} em {count} tabela(s) da aplicação")

    for role in SCHEMA_ROLES:
        sequence_grants = sequence_privileges[role]
        if not sequence_grants["present"]:
            continue
        for privilege, count in sequence_grants["by_privilege"].items():
            if count:
                violations.append(f"{role} tem {privilege} em {count} sequence(s) da aplicação")

    for role in SCHEMA_ROLES:
        routine_grants = routine_privileges[role]
        if not routine_grants["present"]:
            continue
        for privilege, count in routine_grants["by_privilege"].items():
            if count:
                violations.append(f"{role} tem {privilege} em {count} função(ões) da aplicação")

    for entry in default_entries:
        grantee = entry["grantee"]
        object_type = entry["object_type"]
        privilege = entry["privilege"]
        if grantee in SCHEMA_ROLES:
            default_violations.append(
                f"{grantee} recebe {privilege} por default privileges em {object_type}"
            )
        elif grantee == "PUBLIC" and object_type == "FUNCTIONS":
            default_violations.append("PUBLIC tem EXECUTE por default privileges em FUNCTIONS")
    violations.extend(default_violations)

    for view in no_security_invoker:
        warnings.append(f"view {view} sem security_invoker")

    return {
        "ok": not violations,
        "roles": roles,
        "schema_public": schema_acl,
        "app_tables": {
            "total": len(app_tables),
            "with_rls": len(app_tables) - len(missing_rls),
            "missing_rls": missing_rls,
        },
        "table_privileges": privileges,
        "sequences": {
            "total": len(sequences),
            "privileges": sequence_privileges,
        },
        "routines": {
            "total": routines_total,
            "privileges": routine_privileges,
        },
        "default_privileges": {
            "entries": default_entries,
            "violations": default_violations,
        },
        "views": {
            "total": len(views),
            "without_security_invoker": no_security_invoker,
        },
        "violations": violations,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="saída JSON (padrão)")
    parser.parse_args()

    engine: Engine | None = None
    try:
        engine = create_engine(
            _database_url(),
            pool_pre_ping=False,
            connect_args={"connect_timeout": 5},
        )
        report = audit(engine)
    except Exception as exc:  # noqa: BLE001 - a saída é sanitizada de propósito
        print(f"audit_db_security: erro: {_sanitize(exc)}", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
