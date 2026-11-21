"""Serviço de fila e formação transacional de lobbies."""

from __future__ import annotations

import random
import secrets
import uuid
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matches.service import create_match_for_lobby
from app.modules.matchmaking.models import Lobby, LobbyParticipant, MatchmakingRun, QueueEntry
from app.modules.matchmaking.policy import (
    AvailabilityWindow,
    Candidate,
    MeetingRegion,
    RatingBalanceError,
    RegionPoint,
    balance_teams,
    balance_teams_by_rating,
    court_intersection,
    meeting_region,
    select_start,
)
from app.modules.profile.models import (
    COURT_PREFERENCES,
    LEVELS,
    Availability,
    SportFormat,
    UserRegion,
    UserSportProfile,
)
from app.modules.ratings.models import RatingAccount
from app.modules.ratings.trust import TrustService

MMR_ALGORITHM_VERSION = "mmr_v1"
MAX_RANKED_TEAM_SPAN = 800.0
# Nível usado apenas para criar o perfil de um formato que entra na fila
# ranqueada sem perfil. Ranqueada pareia por MMR (ADR 0064).
DEFAULT_RANKED_LEVEL = "intermediate"
DEFAULT_COURT_PREFERENCE = "ANY"


class QueueError(Exception):
    """Erro base da fila de matchmaking."""


class InvalidMode(QueueError):
    """Modo de partida desconhecido."""


class InvalidFormat(QueueError):
    """Formato inexistente ou inativo."""


class SportProfileRequired(QueueError):
    """Usuário não configurou nível para o formato."""


class RegionRequired(QueueError):
    """Usuário não definiu região de busca."""


class AlreadyQueued(QueueError):
    """Já existe entrada ativa para o mesmo usuário, formato e modo."""


class InvalidLevelOverride(QueueError):
    """Nível por entrada inválido ou para combinação fora da seleção."""


class DuplicateSelection(QueueError):
    """Par ``(format_id, mode)`` repetido na seleção explícita."""


class InvalidCourtPreference(QueueError):
    """Preferência de quadra fora de ``PUBLIC_ONLY``/``PRIVATE_ONLY``/``ANY``."""


class LevelNotApplicableForRanked(QueueError):
    """Nível explícito enviado para partida ranqueada.

    Ranqueada pareia por MMR (``ratings``) e divide times por
    ``balance_teams_by_rating``; ``level`` não participa do pareamento. Aceitar
    o campo criaria expectativa falsa, então ele é rejeitado para ``ranked``.
    """


class RankedRestricted(QueueError):
    """Trust Factor restringe temporariamente a fila ranqueada."""


@dataclass(frozen=True)
class RunResult:
    run_id: uuid.UUID
    entries_expired: int
    lobbies_formed: int


@dataclass(frozen=True)
class Formation:
    court: str
    region: MeetingRegion
    start: datetime


class MatchmakingService:
    """Orquestra fila, compatibilidade e criação do lobby."""

    def __init__(
        self,
        session: Session,
        *,
        algorithm_version: str = "level_v1",
        max_radius_km: int = 30,
        search_days: int = 7,
        slot_minutes: int = 30,
        min_lead_minutes: int = 120,
        queue_ttl_hours: int = 24,
        default_timezone: str = "America/Sao_Paulo",
        randomizer: random.Random | None = None,
    ) -> None:
        self._session = session
        self._algorithm = algorithm_version
        self._max_radius = max_radius_km
        self._search_days = search_days
        self._slot_minutes = slot_minutes
        self._min_lead = min_lead_minutes
        self._ttl = timedelta(hours=queue_ttl_hours)
        self._timezone = default_timezone
        # Sorteio uniforme e não determinístico (ADR 0057). Testes podem injetar
        # outro ``random.Random`` sem alterar o comportamento de produção.
        self._random = randomizer or secrets.SystemRandom()
        self._busy: dict[uuid.UUID, list[tuple[datetime, datetime]]] = {}

    # Fila ---------------------------------------------------------------

    def enqueue(
        self,
        user_id: uuid.UUID,
        format_id: uuid.UUID,
        *,
        court_preference: str | None = None,
        mode: str = "casual",
        now: datetime | None = None,
    ) -> QueueEntry:
        if mode not in ("casual", "ranked"):
            raise InvalidMode("modo de partida inválido")
        if court_preference is not None and court_preference not in COURT_PREFERENCES:
            raise InvalidCourtPreference("preferência de quadra inválida")

        sport_format = self._session.get(SportFormat, format_id)
        if sport_format is None or not sport_format.active:
            raise InvalidFormat("formato inexistente ou inativo")

        region = self._session.get(UserRegion, user_id)
        if region is None:
            raise RegionRequired("defina uma região antes de entrar na fila")

        current = ensure_utc(now or utcnow())
        if mode == "ranked" and TrustService(self._session).is_ranked_restricted(
            user_id, now=current
        ):
            raise RankedRestricted("restrição temporária para partidas ranqueadas")
        existing = self._session.scalar(
            select(QueueEntry).where(
                QueueEntry.user_id == user_id,
                QueueEntry.format_id == format_id,
                QueueEntry.mode == mode,
                QueueEntry.status == "waiting",
            )
        )
        if existing is not None:
            raise AlreadyQueued("já existe entrada ativa na fila")

        # A escolha da fila vira a última preferência do perfil (ADR 0064). A
        # criação só acontece depois de todas as validações de erro, para que
        # uma requisição recusada não deixe perfil pendente na sessão. No
        # ``POST`` casual não há nível no payload: sem perfil, continua
        # exigindo que o app informe o nível (``SportProfileRequired``).
        sport_profile = self._upsert_sport_profiles(
            user_id,
            [format_id],
            levels={},
            ranked_formats={format_id} if mode == "ranked" else frozenset(),
            court_preferences=(
                {format_id: court_preference} if court_preference is not None else {}
            ),
        )[format_id]

        entry = QueueEntry(
            user_id=user_id,
            format_id=format_id,
            mode=mode,
            court_preference=court_preference or sport_profile.court_preference,
            level=sport_profile.level,
            status="waiting",
            center_lat=region.center_lat,
            center_lng=region.center_lng,
            radius_km=region.radius_km,
            expires_at=current + self._ttl,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def latest_entry(self, user_id: uuid.UUID) -> QueueEntry | None:
        return self._session.scalar(
            select(QueueEntry)
            .where(
                QueueEntry.user_id == user_id,
                QueueEntry.status.in_(("waiting", "matched")),
            )
            .order_by(QueueEntry.created_at.desc())
            .limit(1)
        )

    def waiting_entries(self, user_id: uuid.UUID) -> list[QueueEntry]:
        """Todas as entradas aguardando do usuário, da mais recente para a mais antiga."""
        return list(
            self._session.scalars(
                select(QueueEntry)
                .where(
                    QueueEntry.user_id == user_id,
                    QueueEntry.status == "waiting",
                )
                .order_by(QueueEntry.created_at.desc(), QueueEntry.id)
            )
        )

    def matched_entries(self, user_id: uuid.UUID) -> list[QueueEntry]:
        """Entradas pareadas cujo lobby continua agendado.

        Só entram as ``matched`` ligadas a um lobby ``scheduled``: partidas
        ``cancelled``/``completed`` são histórico e não devem reaparecer como
        "partida encontrada" no app. Entrada ``matched`` sem ``lobby_id`` também
        é excluída — é um estado inconsistente, não uma partida encontrável.
        Ordem: ``matched_at`` decrescente, com ``created_at``/``id`` como
        desempate.

        Não há filtro por ``expires_at``: esse prazo governa apenas a
        permanência na fila ``waiting``; depois do pareamento, o ciclo de vida é
        do lobby e o horário combinado pode ser posterior ao TTL da entrada.
        """
        return list(
            self._session.scalars(
                select(QueueEntry)
                .join(Lobby, Lobby.id == QueueEntry.lobby_id)
                .where(
                    QueueEntry.user_id == user_id,
                    QueueEntry.status == "matched",
                    Lobby.status == "scheduled",
                )
                .order_by(
                    QueueEntry.matched_at.desc().nulls_last(),
                    QueueEntry.created_at.desc(),
                    QueueEntry.id,
                )
            )
        )

    def replace(
        self,
        user_id: uuid.UUID,
        format_ids: Sequence[uuid.UUID],
        modes: Sequence[str],
        *,
        court_preference: str | None = None,
        levels: Mapping[tuple[uuid.UUID, str], str] | None = None,
        now: datetime | None = None,
    ) -> list[QueueEntry]:
        """Aplica a seleção cartesiana ``formatos × modos`` (compatibilidade).

        Contrato histórico do ``PUT``: cada formato é combinado com cada modo.
        Delega a :meth:`replace_targets`, que concentra validação e diff.
        """
        unique_formats = list(dict.fromkeys(format_ids))
        unique_modes = list(dict.fromkeys(modes))
        for mode in unique_modes:
            if mode not in ("casual", "ranked"):
                raise InvalidMode("modo de partida inválido")
        target = [(format_id, mode) for format_id in unique_formats for mode in unique_modes]
        return self.replace_targets(
            user_id,
            target,
            court_preference=court_preference,
            levels=levels,
            now=now,
        )

    def replace_targets(
        self,
        user_id: uuid.UUID,
        targets: Sequence[tuple[uuid.UUID, str]],
        *,
        court_preference: str | None = None,
        court_preferences: Mapping[tuple[uuid.UUID, str], str] | None = None,
        levels: Mapping[tuple[uuid.UUID, str], str] | None = None,
        now: datetime | None = None,
    ) -> list[QueueEntry]:
        """Aplica uma lista explícita de pares ``(format_id, mode)``, atomicamente.

        Valida tudo antes de escrever. Depois compara os pares com as entradas
        ``waiting`` existentes:

        - par que permanece: a **mesma linha** é preservada (mesmo ``id``,
          ``created_at`` e ``matched_at``), atualizando apenas os campos
          explícitos do payload;
        - par novo: é criado;
        - par que saiu: é cancelado.

        ``levels`` mapeia ``(format_id, mode)`` para um nível explícito, apenas
        em pares casuais. Só é aceito para pares da seleção; par ranqueado com
        override é rejeitado (ranqueada pareia por MMR, não por nível). O nível
        casual também passa a ser a última preferência do perfil esportivo
        daquele formato (ADR 0064); par ranqueado sem perfil usa
        ``intermediate`` como default e nunca sobrescreve nível já salvo.
        Preservar ``created_at`` é o que sustenta o cronômetro de espera no
        app. Lista vazia apenas cancela a seleção. Par repetido é rejeitado:
        duas entradas para a mesma combinação seriam ambíguas.

        ``court_preferences`` mapeia ``(format_id, mode)`` para a preferência
        de quadra daquele par (ADR 0067); o item vence o ``court_preference``
        global. A preferência efetiva também alimenta o perfil do formato. Se o
        mesmo formato aparece em mais de um par com valores diferentes, o perfil
        grava o último par na ordem da seleção; cada entrada guarda o seu.
        """
        target = list(dict.fromkeys(targets))
        if len(target) != len(targets):
            raise DuplicateSelection("par formato/modo repetido na seleção")
        for _, mode in target:
            if mode not in ("casual", "ranked"):
                raise InvalidMode("modo de partida inválido")
        override_levels = dict(levels or {})
        for override_level in override_levels.values():
            if override_level not in LEVELS:
                raise InvalidLevelOverride("nível de entrada inválido")
        wanted = set(target)
        item_preferences = dict(court_preferences or {})
        if court_preference is not None and court_preference not in COURT_PREFERENCES:
            raise InvalidCourtPreference("preferência de quadra inválida")
        for key, preference in item_preferences.items():
            if preference not in COURT_PREFERENCES:
                raise InvalidCourtPreference("preferência de quadra inválida")
            if key not in wanted:
                raise InvalidCourtPreference("preferência de quadra fora da seleção")
        # ``level`` só governa o pareamento casual (balance_teams por nível).
        # Ranqueada usa MMR e divisão por rating; override de nível nela seria
        # ignorado silenciosamente, então é rejeitado antes de qualquer escrita.
        if any(key in wanted and key[1] == "ranked" for key in override_levels):
            raise LevelNotApplicableForRanked("nível não se aplica a partida ranqueada")

        current = ensure_utc(now or utcnow())
        unique_formats = list(dict.fromkeys(format_id for format_id, _ in target))
        region = self._session.get(UserRegion, user_id)
        if target:
            if region is None:
                raise RegionRequired("defina uma região antes de entrar na fila")
            for format_id in unique_formats:
                sport_format = self._session.get(SportFormat, format_id)
                if sport_format is None or not sport_format.active:
                    raise InvalidFormat("formato inexistente ou inativo")
            if any(mode == "ranked" for _, mode in target) and TrustService(
                self._session
            ).is_ranked_restricted(user_id, now=current):
                raise RankedRestricted("restrição temporária para partidas ranqueadas")

        if any(key not in wanted for key in override_levels):
            raise InvalidLevelOverride("override de nível fora da seleção")

        if not target:
            self._cancel_waiting(user_id, current)
            return []

        if region is None:
            # Inalcançável: a validação acima já exigiria a região. Mantido
            # explícito para o type checker, sem depender de ``assert``.
            raise RegionRequired("defina uma região antes de entrar na fila")

        # Preferência efetiva de cada par: item de ``selections[]`` vence o
        # global legado (ADR 0067). Um formato pode ter pares em modos
        # diferentes; cada entrada usa a sua, e o perfil grava a última na ordem.
        effective_preferences: dict[tuple[uuid.UUID, str], str | None] = {
            key: item_preferences.get(key, court_preference) for key in target
        }
        profile_preferences: dict[uuid.UUID, str] = {}
        for key, pair_preference in effective_preferences.items():
            if pair_preference is not None:
                profile_preferences[key[0]] = pair_preference

        # A escolha da fila vira a última preferência do perfil (ADR 0064),
        # somente para os formatos que entram na fila. Feito depois de todas as
        # validações de erro e dentro da mesma transação da fila: falha no
        # ``PUT`` não persiste perfil.
        profiles = self._upsert_sport_profiles(
            user_id,
            unique_formats,
            levels={
                format_id: level
                for (format_id, mode), level in override_levels.items()
                if mode == "casual"
            },
            ranked_formats={format_id for format_id, mode in target if mode == "ranked"},
            court_preferences=profile_preferences,
        )

        existing = list(
            self._session.scalars(
                select(QueueEntry)
                .where(
                    QueueEntry.user_id == user_id,
                    QueueEntry.status == "waiting",
                )
                .order_by(QueueEntry.created_at, QueueEntry.id)
            )
        )
        kept: dict[tuple[uuid.UUID, str], QueueEntry] = {}
        removed: list[QueueEntry] = []
        for entry in existing:
            key = (entry.format_id, entry.mode)
            if key in wanted and key not in kept:
                kept[key] = entry
            else:
                # Fora da nova seleção (ou duplicata histórica): cancelar.
                removed.append(entry)
        self._cancel_entries(removed, current)

        entries: list[QueueEntry] = []
        for format_id, mode in target:
            # Sem override explícito, o nível é o do perfil já atualizado pela
            # escolha casual desta requisição (ADR 0064), inclusive para a
            # entrada preservada pelo diff.
            level = override_levels.get((format_id, mode), profiles[format_id].level)
            pair_preference = effective_preferences[(format_id, mode)]
            preserved = kept.get((format_id, mode))
            if preserved is not None:
                self._refresh_entry(
                    preserved,
                    court_preference=pair_preference,
                    level=level,
                )
                entries.append(preserved)
                continue
            entries.append(
                self._build_entry(
                    user_id,
                    format_id,
                    mode,
                    profiles[format_id],
                    region,
                    court_preference=pair_preference,
                    level=level,
                    now=current,
                )
            )
        self._session.flush()
        return entries

    def _upsert_sport_profiles(
        self,
        user_id: uuid.UUID,
        format_ids: Sequence[uuid.UUID],
        *,
        levels: Mapping[uuid.UUID, str],
        ranked_formats: Collection[uuid.UUID],
        court_preferences: Mapping[uuid.UUID, str],
    ) -> dict[uuid.UUID, UserSportProfile]:
        """Cria/atualiza o perfil esportivo a partir da escolha da fila (ADR 0064).

        ``levels`` traz apenas níveis casuais explícitos. Regras:

        - casual com nível explícito: grava o nível no perfil (última
          preferência vence);
        - ranqueada sem perfil: cria com ``intermediate`` e mantém o nível
          existente quando já houver perfil (ranqueada pareia por MMR);
        - ``court_preferences`` traz a preferência efetiva de cada formato
          (item de ``selections[]`` ou global legado) e atualiza somente esses
          formatos; formato sem preferência preserva a existente, e a criação
          usa ``ANY``;
        - formato selecionado apenas em casual, sem nível explícito e sem
          perfil continua respondendo ``SportProfileRequired``.

        Os formatos fora de ``format_ids`` não são tocados. A sessão é a mesma
        da fila e o ``PUT``/``POST`` só faz commit depois; qualquer erro antes
        do commit é desfeito pelo ``rollback`` da rota.
        """
        existing = {
            profile.format_id: profile
            for profile in self._session.scalars(
                select(UserSportProfile).where(
                    UserSportProfile.user_id == user_id,
                    UserSportProfile.format_id.in_(list(format_ids)),
                )
            )
        }
        for format_id in format_ids:
            if (
                format_id not in existing
                and format_id not in levels
                and format_id not in ranked_formats
            ):
                raise SportProfileRequired("defina nível e preferência para o formato")

        profiles: dict[uuid.UUID, UserSportProfile] = {}
        for format_id in format_ids:
            profile = existing.get(format_id)
            preference = court_preferences.get(format_id)
            if profile is None:
                profile = UserSportProfile(
                    user_id=user_id,
                    format_id=format_id,
                    level=levels.get(format_id, DEFAULT_RANKED_LEVEL),
                    court_preference=preference or DEFAULT_COURT_PREFERENCE,
                )
                self._session.add(profile)
            else:
                level = levels.get(format_id)
                if level is not None:
                    profile.level = level
                if preference is not None:
                    profile.court_preference = preference
            profiles[format_id] = profile
        return profiles

    def _refresh_entry(
        self,
        entry: QueueEntry,
        *,
        court_preference: str | None,
        level: str,
    ) -> None:
        """Atualiza no lugar os campos derivados da requisição.

        ``center_lat``, ``center_lng`` e ``radius_km`` não fazem parte do
        contrato do ``PUT`` (§23.1): continuam vindo da região gravada no
        servidor, nunca do corpo. ``level`` vem do override da combinação ou,
        sem override, do perfil esportivo atual. A linha preservada mantém
        ``created_at``, ``matched_at`` e ``expires_at`` originais.
        """
        if court_preference is not None:
            entry.court_preference = court_preference
        entry.level = level

    def _build_entry(
        self,
        user_id: uuid.UUID,
        format_id: uuid.UUID,
        mode: str,
        sport_profile: UserSportProfile,
        region: UserRegion,
        *,
        court_preference: str | None,
        level: str,
        now: datetime,
    ) -> QueueEntry:
        entry = QueueEntry(
            user_id=user_id,
            format_id=format_id,
            mode=mode,
            court_preference=court_preference or sport_profile.court_preference,
            level=level,
            status="waiting",
            center_lat=region.center_lat,
            center_lng=region.center_lng,
            radius_km=region.radius_km,
            expires_at=now + self._ttl,
        )
        self._session.add(entry)
        return entry

    def leave(self, user_id: uuid.UUID) -> bool:
        """Cancela todas as entradas aguardando do usuário."""
        return self._cancel_waiting(user_id, ensure_utc(utcnow())) > 0

    def _cancel_entries(self, entries: Sequence[QueueEntry], now: datetime) -> int:
        """Cancela apenas linhas ainda ``waiting`` no momento da escrita.

        O ``WHERE status = 'waiting'`` evita sobrescrever uma entrada que o
        worker pareou concorrentemente: entrada ``matched`` nunca é cancelada
        pela troca de seleção.
        """
        if not entries:
            return 0
        result = cast(
            "CursorResult[Any]",
            self._session.execute(
                update(QueueEntry)
                .where(
                    QueueEntry.id.in_([entry.id for entry in entries]),
                    QueueEntry.status == "waiting",
                )
                .values(status="cancelled", updated_at=now)
                .execution_options(synchronize_session="fetch")
            ),
        )
        # Cancela antes de inserir para não colidir com o índice único parcial.
        self._session.flush()
        return int(result.rowcount or 0)

    def _cancel_waiting(self, user_id: uuid.UUID, now: datetime) -> int:
        entries = list(
            self._session.scalars(
                select(QueueEntry).where(
                    QueueEntry.user_id == user_id,
                    QueueEntry.status == "waiting",
                )
            )
        )
        return self._cancel_entries(entries, now)

    # Worker -------------------------------------------------------------

    def run_once(self, now: datetime | None = None) -> RunResult:
        current = ensure_utc(now or utcnow())
        run = MatchmakingRun(status="running", algorithm_version=self._algorithm)
        self._session.add(run)
        self._session.flush()

        try:
            expired = self._expire(current)
            with self._session.begin_nested():
                formed = self._form_all(current)
            run.entries_expired = expired
            run.lobbies_formed = formed
            run.status = "completed"
            run.finished_at = utcnow()
            self._session.flush()
            return RunResult(
                run_id=run.id,
                entries_expired=expired,
                lobbies_formed=formed,
            )
        except Exception:
            run.status = "failed"
            run.finished_at = utcnow()
            self._session.flush()
            raise

    def _expire(self, now: datetime) -> int:
        result = cast(
            "CursorResult[Any]",
            self._session.execute(
                update(QueueEntry)
                .where(QueueEntry.status == "waiting", QueueEntry.expires_at <= now)
                .values(status="expired", updated_at=now)
                .execution_options(synchronize_session=False)
            ),
        )
        return int(result.rowcount or 0)

    def _form_all(self, now: datetime) -> int:
        groups: dict[tuple[uuid.UUID, str], list[QueueEntry]] = defaultdict(list)
        waiting = self._lock_waiting(now)
        # O pool considera TODAS as entradas `waiting`, nunca apenas a mais
        # recente do usuário.
        for entry in waiting:
            groups[(entry.format_id, entry.mode)].append(entry)

        self._busy = self._load_busy({entry.user_id for entry in waiting}, now)
        # Sorteio uniforme da ordem dos grupos: quando um usuário tem entradas
        # elegíveis em mais de um grupo, só uma vira lobby neste ciclo e a
        # escolhida não depende da ordem de criação (ADR 0057).
        group_keys = list(groups)
        self._random.shuffle(group_keys)

        formed = 0
        matched_users: set[uuid.UUID] = set()
        for format_id, mode in group_keys:
            sport_format = self._session.get(SportFormat, format_id)
            if sport_format is None or not sport_format.active:
                continue
            ratings = self._ratings_for_format(format_id) if mode == "ranked" else None
            formed += self._form_group(
                sport_format,
                mode,
                groups[(format_id, mode)],
                now,
                ratings=ratings,
                exclude_users=matched_users,
            )
        return formed

    def _load_busy(
        self,
        user_ids: set[uuid.UUID],
        now: datetime,
    ) -> dict[uuid.UUID, list[tuple[datetime, datetime]]]:
        """Tempo já comprometido de cada participante.

        A autoridade é o **lobby**, não a reserva: ``bookings.lobby_id`` é único
        (1:1) e o horário é fixado em ``Lobby.scheduled_start_at``. O critério é
        temporal — qualquer lobby de matchmaking ou manual que ainda não
        terminou conta, exceto ``cancelled``. ``completed`` com horário futuro
        continua ocupando pelo intervalo; ``completed`` no passado já é
        descartado por ``scheduled_end_at > now``.
        """
        busy: dict[uuid.UUID, list[tuple[datetime, datetime]]] = defaultdict(list)
        if not user_ids:
            return busy
        rows = self._session.execute(
            select(
                LobbyParticipant.user_id,
                Lobby.scheduled_start_at,
                Lobby.scheduled_end_at,
            )
            .join(Lobby, Lobby.id == LobbyParticipant.lobby_id)
            .where(
                LobbyParticipant.user_id.in_(user_ids),
                Lobby.origin.in_(("matchmaking", "manual")),
                Lobby.status != "cancelled",
                Lobby.scheduled_end_at > now,
            )
        )
        for user_id, start, end in rows:
            busy[user_id].append((ensure_utc(start), ensure_utc(end)))
        return busy

    def _ratings_for_format(self, format_id: uuid.UUID) -> dict[uuid.UUID, float]:
        rows = self._session.execute(
            select(RatingAccount.user_id, RatingAccount.rating).where(
                RatingAccount.format_id == format_id
            )
        )
        return {user_id: rating for user_id, rating in rows}

    def _lock_waiting(self, now: datetime) -> list[QueueEntry]:
        statement = (
            select(QueueEntry)
            .where(QueueEntry.status == "waiting", QueueEntry.expires_at > now)
            .order_by(QueueEntry.created_at, QueueEntry.id)
        )
        if self._session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        return list(self._session.scalars(statement))

    def _form_group(
        self,
        sport_format: SportFormat,
        mode: str,
        entries: Sequence[QueueEntry],
        now: datetime,
        *,
        ratings: dict[uuid.UUID, float] | None = None,
        exclude_users: set[uuid.UUID] | None = None,
    ) -> int:
        needed = sport_format.total_participants
        if needed < 2:
            return 0

        pending = [
            entry
            for entry in entries
            if exclude_users is None or entry.user_id not in exclude_users
        ]
        formed = 0
        while len(pending) >= needed:
            base = pending[0]
            selected = [base]
            formation: Formation | None = None
            candidates = pending[1:]
            if mode == "ranked" and ratings is not None:
                anchor_rating = ratings.get(base.user_id, 1500.0)
                candidates = sorted(
                    candidates,
                    key=lambda entry: (
                        abs(ratings.get(entry.user_id, 1500.0) - anchor_rating),
                        entry.created_at,
                        str(entry.id),
                    ),
                )
            for candidate in candidates:
                if len(selected) == needed:
                    break
                trial = [*selected, candidate]
                trial_formation = self._evaluate(trial, sport_format, now)
                if trial_formation is not None:
                    selected.append(candidate)
                    formation = trial_formation
            if len(selected) != needed or formation is None:
                # A entrada mais antiga não fecha grupo; tenta a próxima sem bloqueá-la.
                pending = pending[1:]
                continue

            teams = None
            if mode == "ranked" and ratings is not None:
                try:
                    teams = balance_teams_by_rating(
                        [(entry.user_id, ratings.get(entry.user_id, 1500.0)) for entry in selected],
                        team_size=needed // 2,
                        max_span=MAX_RANKED_TEAM_SPAN,
                    )
                except RatingBalanceError:
                    pending = pending[1:]
                    continue

            self._create_lobby(
                sport_format,
                mode,
                selected,
                formation,
                now,
                ratings=ratings,
                teams=teams,
            )
            if exclude_users is not None:
                exclude_users.update(entry.user_id for entry in selected)
            formed += 1
            pending = [entry for entry in pending if entry not in selected]
        return formed

    def _evaluate(
        self,
        entries: Sequence[QueueEntry],
        sport_format: SportFormat,
        now: datetime,
    ) -> Formation | None:
        court = court_intersection(entry.court_preference for entry in entries)
        if court is None:
            return None

        region = meeting_region(
            [
                RegionPoint(
                    lat=entry.center_lat,
                    lng=entry.center_lng,
                    radius_km=entry.radius_km,
                )
                for entry in entries
            ],
            self._max_radius,
        )
        if region is None:
            return None

        availability = [self._availability(entry.user_id) for entry in entries]
        blocked = [interval for entry in entries for interval in self._busy.get(entry.user_id, ())]
        start = select_start(
            availability,
            duration_minutes=sport_format.duration_minutes,
            now=now,
            search_days=self._search_days,
            slot_minutes=self._slot_minutes,
            min_lead_minutes=self._min_lead,
            default_timezone=self._timezone,
            blocked=blocked,
        )
        if start is None:
            return None
        return Formation(court=court, region=region, start=start)

    def _availability(self, user_id: uuid.UUID) -> list[AvailabilityWindow]:
        rows = self._session.scalars(select(Availability).where(Availability.user_id == user_id))
        return [
            AvailabilityWindow(
                weekday=row.weekday,
                start_time=row.start_time,
                end_time=row.end_time,
                timezone=row.timezone,
            )
            for row in rows
        ]

    def _create_lobby(
        self,
        sport_format: SportFormat,
        mode: str,
        entries: Sequence[QueueEntry],
        formation: Formation,
        now: datetime,
        *,
        ratings: dict[uuid.UUID, float] | None = None,
        teams: dict[uuid.UUID, int] | None = None,
    ) -> Lobby:
        algorithm_version = MMR_ALGORITHM_VERSION if mode == "ranked" else self._algorithm
        lobby = Lobby(
            format_id=sport_format.id,
            format_version=sport_format.version,
            origin="matchmaking",
            mode=mode,
            status="scheduled",
            court_preference=formation.court,
            scheduled_start_at=formation.start,
            scheduled_end_at=formation.start + timedelta(minutes=sport_format.duration_minutes),
            duration_minutes=sport_format.duration_minutes,
            center_lat=formation.region.lat,
            center_lng=formation.region.lng,
            radius_km=formation.region.radius_km,
            algorithm_version=algorithm_version,
        )
        self._session.add(lobby)
        self._session.flush()

        if teams is None:
            if mode == "ranked":
                teams = balance_teams_by_rating(
                    [
                        (
                            entry.user_id,
                            (ratings or {}).get(entry.user_id, 1500.0),
                        )
                        for entry in entries
                    ],
                    team_size=sport_format.total_participants // 2,
                    max_span=MAX_RANKED_TEAM_SPAN,
                )
            else:
                teams = balance_teams(
                    [
                        Candidate(
                            user_id=entry.user_id,
                            level=entry.level,
                            region=RegionPoint(entry.center_lat, entry.center_lng, entry.radius_km),
                        )
                        for entry in entries
                    ]
                )
        participants: list[LobbyParticipant] = []
        for entry in entries:
            participant = LobbyParticipant(
                lobby_id=lobby.id,
                user_id=entry.user_id,
                queue_entry_id=entry.id,
                team=teams[entry.user_id],
                level=entry.level,
            )
            participants.append(participant)
            self._session.add(participant)
            entry.status = "matched"
            entry.lobby_id = lobby.id
            entry.matched_at = now
            entry.updated_at = now
        # O tempo passa a estar comprometido para todos os participantes, mesmo
        # que outras entradas do mesmo usuário continuem `waiting`.
        lobby_end = formation.start + timedelta(minutes=sport_format.duration_minutes)
        for entry in entries:
            self._busy.setdefault(entry.user_id, []).append((formation.start, lobby_end))
        self._session.flush()
        create_match_for_lobby(self._session, lobby, participants, now=now)
        return lobby
