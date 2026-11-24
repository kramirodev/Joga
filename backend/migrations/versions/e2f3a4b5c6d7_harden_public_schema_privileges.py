"""fecha a exposição do schema ``public`` para os papéis da Data API

Revision ID: e2f3a4b5c6d7
Revises: d9e0f1a2b3c4
Create Date: 2026-11-24 18:30:00.000000

O JOGA usa o Supabase apenas como PostgreSQL gerenciado. O backend conecta
diretamente pelo Session pooler com o papel ``postgres`` (owner do banco), e o
aplicativo nunca acessa o banco. A Data API do Supabase (PostgREST), a anon key
e o papel ``service_role`` não fazem parte da arquitetura.

Por isso, o schema ``public`` não deve ser alcançável por ``PUBLIC``, ``anon``
ou ``authenticated``. Esta migração:

* revoga ``USAGE``/``CREATE`` no schema ``public``;
* revoga privilégios de tabelas, views, materialized views, foreign tables e
  sequências cujo dono é o papel que executa a migração;
* habilita RLS nas tabelas de ``public`` (sem ``FORCE``: o owner continua
  lendo/escrevendo normalmente). Isso inclui ``alembic_version``: o Alembic
  roda como owner/BYPASSRLS, então continua atualizando o controle de versão;
* marca views como ``security_invoker`` para que respeitem as permissões de
  quem consulta;
* revoga ``EXECUTE`` de funções/procedures do app;
* remove privilégios padrão (``ALTER DEFAULT PRIVILEGES``) para que tabelas,
  sequências e funções criadas no futuro não voltem a ser expostas.

Objetos de extensões instaladas por ``supabase_admin`` (por exemplo
``spatial_ref_sys`` e funções do PostGIS) não pertencem a este papel e não são
alterados. A revogação de ``USAGE`` no schema já os torna inalcançáveis por
``anon``/``authenticated``. ``service_role`` não é tocado.

O teste ``test_db_security_hardening.py`` e o script
``scripts/audit_db_security.py`` cobrem RLS, ``USAGE`` do schema, tabelas,
views, sequences, funções/procedures e default privileges.

O downgrade é intencionalmente no-op: reabrir o schema exigiria uma decisão
explícita de segurança, não uma reversão automática de migração.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Papéis criados pelo Supabase. ``PUBLIC`` é sempre incluído; ``anon`` e
# ``authenticated`` só entram se existirem no cluster (Postgres local/CI não os
# cria). A lista é montada dentro de cada DO block para que a migração continue
# idempotente e portátil.
_HARDEN_SCHEMA = """
DO $hardening$
DECLARE
    roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ' ORDER BY rolname)
      INTO roles
      FROM pg_roles
     WHERE rolname IN ('anon', 'authenticated');

    roles := 'PUBLIC' || COALESCE(', ' || roles, '');

    EXECUTE format('REVOKE USAGE, CREATE ON SCHEMA public FROM %s', roles);
END
$hardening$;
"""

_HARDEN_RELATIONS = """
DO $hardening$
DECLARE
    rel record;
    roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ' ORDER BY rolname)
      INTO roles
      FROM pg_roles
     WHERE rolname IN ('anon', 'authenticated');

    roles := 'PUBLIC' || COALESCE(', ' || roles, '');

    FOR rel IN
        SELECT c.oid,
               c.relkind,
               format('%I.%I', n.nspname, c.relname) AS qualified_name
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND pg_get_userbyid(c.relowner) = current_user
         ORDER BY n.nspname, c.relname
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON TABLE %s FROM %s',
            rel.qualified_name,
            roles
        );

        IF rel.relkind IN ('r', 'p') THEN
            -- Sem FORCE: o owner do banco precisa continuar ignorando RLS.
            EXECUTE format(
                'ALTER TABLE %s ENABLE ROW LEVEL SECURITY',
                rel.qualified_name
            );
        ELSIF rel.relkind = 'v' THEN
            EXECUTE format(
                'ALTER VIEW %s SET (security_invoker = true)',
                rel.qualified_name
            );
        END IF;
    END LOOP;
END
$hardening$;
"""

_HARDEN_SEQUENCES = """
DO $hardening$
DECLARE
    seq record;
    roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ' ORDER BY rolname)
      INTO roles
      FROM pg_roles
     WHERE rolname IN ('anon', 'authenticated');

    roles := 'PUBLIC' || COALESCE(', ' || roles, '');

    FOR seq IN
        SELECT format('%I.%I', n.nspname, c.relname) AS qualified_name
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relkind = 'S'
           AND pg_get_userbyid(c.relowner) = current_user
         ORDER BY n.nspname, c.relname
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON SEQUENCE %s FROM %s',
            seq.qualified_name,
            roles
        );
    END LOOP;
END
$hardening$;
"""

_HARDEN_ROUTINES = """
DO $hardening$
DECLARE
    routine record;
    roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ' ORDER BY rolname)
      INTO roles
      FROM pg_roles
     WHERE rolname IN ('anon', 'authenticated');

    roles := 'PUBLIC' || COALESCE(', ' || roles, '');

    FOR routine IN
        SELECT format(
                   '%I.%I(%s)',
                   n.nspname,
                   p.proname,
                   pg_get_function_identity_arguments(p.oid)
               ) AS signature
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.prokind IN ('f', 'p')
           AND pg_get_userbyid(p.proowner) = current_user
         ORDER BY n.nspname, p.proname, p.oid
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ROUTINE %s FROM %s',
            routine.signature,
            roles
        );
    END LOOP;
END
$hardening$;
"""

_HARDEN_DEFAULT_PRIVILEGES = """
DO $hardening$
DECLARE
    roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ' ORDER BY rolname)
      INTO roles
      FROM pg_roles
     WHERE rolname IN ('anon', 'authenticated');

    roles := 'PUBLIC' || COALESCE(', ' || roles, '');

    -- Sem FOR ROLE: vale para o papel que executa a migração (o dono das
    -- tabelas da aplicação). Default privileges de outros papéis, como
    -- supabase_admin, não podem ser alterados por este papel.
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %s',
        roles
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %s',
        roles
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %s',
        roles
    );
END
$hardening$;
"""


def upgrade() -> None:
    op.execute(_HARDEN_SCHEMA)
    op.execute(_HARDEN_RELATIONS)
    op.execute(_HARDEN_SEQUENCES)
    op.execute(_HARDEN_ROUTINES)
    op.execute(_HARDEN_DEFAULT_PRIVILEGES)


def downgrade() -> None:
    """Mantém o endurecimento: reabrir o schema exige decisão explícita."""
