"""Regressão do endurecimento do schema ``public`` (Supabase/PostgreSQL).

Executado depois de ``alembic upgrade head`` no banco apontado por
``JOGA_TEST_DATABASE_URL``. O teste é somente leitura e não depende das
tabelas de outros testes: ele inspeciona o schema ``public`` diretamente.

Objetos instalados por extensões (PostGIS, pgcrypto etc.) e o controle de
versão do Alembic não fazem parte da aplicação e ficam de fora das asserções
de privilégio. O novo teste também cobre sequences, funções/procedures e
default privileges. O owner do banco precisa continuar lendo; por isso a
migração habilita RLS sem ``FORCE``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
APPLICATION_ROLES = ("anon", "authenticated")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL
    or not TEST_DATABASE_URL.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")),
    reason="JOGA_TEST_DATABASE_URL não aponta para PostgreSQL",
)

APP_RELATIONS = """
    SELECT c.oid, c.relname
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind IN ('r', 'p')
       AND c.relname NOT IN ('spatial_ref_sys', 'alembic_version')
       AND NOT EXISTS (
           SELECT 1
             FROM pg_depend d
            WHERE d.classid = 'pg_class'::regclass
              AND d.objid = c.oid
              AND d.deptype = 'e'
       )
"""

APP_SEQUENCES = """
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

APP_ROUTINES = """
    SELECT p.oid, p.proname
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.prokind IN ('f', 'p')
       AND pg_get_userbyid(p.proowner) = current_user
"""

DEFAULT_PRIVILEGES = """
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


def _psycopg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert TEST_DATABASE_URL is not None
    database_engine = create_engine(_psycopg_url(TEST_DATABASE_URL), pool_pre_ping=True)
    if database_engine.dialect.name != "postgresql":
        database_engine.dispose()
        pytest.skip("JOGA_TEST_DATABASE_URL não aponta para PostgreSQL")
    yield database_engine
    database_engine.dispose()


def _role_exists(connection: Connection, role: str) -> bool:
    return bool(
        connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar()
    )


def test_tables_owned_by_current_user_have_rls(engine: Engine) -> None:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT c.relname
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public'
                   AND c.relkind IN ('r', 'p')
                   AND pg_get_userbyid(c.relowner) = current_user
                   AND NOT c.relrowsecurity
                 ORDER BY c.relname
                """
            )
        )
        missing = [str(row.relname) for row in rows]
    assert missing == [], f"tabelas sem RLS em public: {missing}"


def test_public_role_has_no_usage_on_public_schema(engine: Engine) -> None:
    with engine.connect() as connection:
        granted = connection.execute(
            text(
                """
                SELECT acl.privilege_type
                  FROM pg_namespace AS n
                  CROSS JOIN LATERAL aclexplode(
                      coalesce(n.nspacl, acldefault('n', n.nspowner))
                  ) AS acl
                 WHERE n.nspname = 'public'
                   AND acl.grantee = 0
                   AND acl.privilege_type = 'USAGE'
                """
            )
        ).scalar()
    assert granted is None, "PUBLIC ainda tem USAGE no schema public"


def test_application_roles_have_no_access(engine: Engine) -> None:
    with engine.connect() as connection:
        for role in APPLICATION_ROLES:
            if not _role_exists(connection, role):
                continue

            usage = connection.execute(
                text("SELECT has_schema_privilege(CAST(:role AS name), 'public', 'USAGE')"),
                {"role": role},
            ).scalar()
            assert not usage, f"{role} ainda tem USAGE no schema public"

            rows = connection.execute(
                text(
                    f"""
                    SELECT rel.relname, privilege.privilege
                      FROM ({APP_RELATIONS}) AS rel
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
            grants = [(str(row.relname), str(row.privilege)) for row in rows]
            assert grants == [], f"{role} ainda tem privilégios em tabelas do app: {grants}"


def test_application_roles_have_no_sequence_privileges(engine: Engine) -> None:
    with engine.connect() as connection:
        for role in APPLICATION_ROLES:
            if not _role_exists(connection, role):
                continue
            rows = connection.execute(
                text(
                    f"""
                    SELECT seq.relname, privilege.privilege
                      FROM ({APP_SEQUENCES}) AS seq
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
            grants = [(str(row.relname), str(row.privilege)) for row in rows]
            assert grants == [], f"{role} ainda tem privilégios em sequences: {grants}"


def test_application_roles_have_no_routine_privileges(engine: Engine) -> None:
    with engine.connect() as connection:
        for role in APPLICATION_ROLES:
            if not _role_exists(connection, role):
                continue
            rows = connection.execute(
                text(
                    f"""
                    SELECT routine.proname
                      FROM ({APP_ROUTINES}) AS routine
                     WHERE has_function_privilege(
                               CAST(:role AS name),
                               routine.oid,
                               'EXECUTE'
                           )
                     ORDER BY routine.proname
                    """
                ),
                {"role": role},
            )
            grants = [str(row.proname) for row in rows]
            assert grants == [], f"{role} ainda tem EXECUTE em funções: {grants}"


def test_default_privileges_have_no_api_grants(engine: Engine) -> None:
    with engine.connect() as connection:
        rows = list(connection.execute(text(DEFAULT_PRIVILEGES)))

    api_grants = [
        (str(row.object_type), str(row.grantee), str(row.privilege_type))
        for row in rows
        if str(row.grantee) in APPLICATION_ROLES
    ]
    assert api_grants == [], f"default privileges para papéis da API: {api_grants}"

    public_function_grants = [
        (str(row.object_type), str(row.privilege_type))
        for row in rows
        if str(row.grantee) == "PUBLIC" and str(row.object_type) == "FUNCTIONS"
    ]
    assert public_function_grants == [], (
        f"PUBLIC ainda recebe EXECUTE por default privileges em funções: {public_function_grants}"
    )


def test_owner_can_still_read_application_tables(engine: Engine) -> None:
    with engine.connect() as connection:
        relname = connection.execute(
            text(f"SELECT relname FROM ({APP_RELATIONS}) AS rel ORDER BY relname LIMIT 1")
        ).scalar()
        if relname is None:
            pytest.skip("nenhuma tabela da aplicação em public")
        allowed = connection.execute(
            text(
                "SELECT has_table_privilege("
                "current_user, to_regclass(format('%I.%I', 'public', CAST(:table AS text))), "
                "'SELECT')"
            ),
            {"table": str(relname)},
        ).scalar()
        assert allowed, f"owner perdeu SELECT em public.{relname}"
        # O owner ignora RLS porque a migração não usa FORCE ROW LEVEL SECURITY.
        quoted = connection.dialect.identifier_preparer.quote(str(relname))
        connection.exec_driver_sql(f"SELECT 1 FROM public.{quoted} LIMIT 1").all()
