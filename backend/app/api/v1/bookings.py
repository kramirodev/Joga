"""Endpoints de reservas, bloqueios e temporizadores (Fase 13A)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.service import (
    BookingBundle,
    BookingConflict,
    BookingError,
    BookingForbidden,
    BookingInvalid,
    BookingNotFound,
    BookingService,
    BookingTransitionError,
)
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.organizations.service import Forbidden, OrganizationNotFound

router = APIRouter(tags=["bookings"])


class BookingCreate(BaseModel):
    lobby_id: UUID
    organization_venue_id: UUID
    venue_space_id: UUID
    starts_at: datetime
    ends_at: datetime


class ParticipantConfirmation(BaseModel):
    decision: Literal["CONFIRM", "DECLINE"]


class SubstitutionCreate(BaseModel):
    replace_user_id: UUID
    new_user_id: UUID


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class ParticipantView(BaseModel):
    user_id: UUID
    seat: int
    active: bool
    contribution_cents: int
    payment_status: str
    confirmed_at: datetime | None
    declined_at: datetime | None
    replaced_by_user_id: UUID | None


class TimerView(BaseModel):
    timer_type: str
    status: str
    started_at: datetime
    deadline_at: datetime
    ended_at: datetime | None


class HoldView(BaseModel):
    id: UUID
    space_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: str
    released_at: datetime | None


class PaymentView(BaseModel):
    id: UUID
    participant_id: UUID
    version: int
    amount_cents: int
    status: str
    paid_at: datetime | None


class BookingView(BaseModel):
    id: UUID
    lobby_id: UUID
    organization_id: UUID
    organization_venue_id: UUID
    venue_space_id: UUID
    status: str
    starts_at: datetime
    ends_at: datetime
    price_cents: int
    currency: str
    seats: int
    policy_version: str
    cancellation_policy: str
    response_due_at: datetime | None
    payment_due_at: datetime | None
    hold_expires_at: datetime | None
    accepted_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    expired_at: datetime | None
    completed_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    participants: list[ParticipantView]
    timers: list[TimerView]
    hold: HoldView | None
    payments: list[PaymentView]


class BookingListResponse(BaseModel):
    bookings: list[BookingView]


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    mapping = {
        BookingNotFound: ("booking_not_found", status.HTTP_404_NOT_FOUND),
        OrganizationNotFound: ("organization_not_found", status.HTTP_404_NOT_FOUND),
        BookingForbidden: ("forbidden", status.HTTP_403_FORBIDDEN),
        Forbidden: ("forbidden", status.HTTP_403_FORBIDDEN),
        BookingInvalid: ("invalid_input", status.HTTP_422_UNPROCESSABLE_CONTENT),
        BookingTransitionError: ("invalid_transition", status.HTTP_409_CONFLICT),
        BookingConflict: (getattr(exc, "code", "booking_conflict"), status.HTTP_409_CONFLICT),
        BookingError: ("booking_error", status.HTTP_409_CONFLICT),
    }
    for error_type, (code, status_code) in mapping.items():
        if isinstance(exc, error_type):
            return _error(code, status_code)
    raise exc


def _view(
    bundle: BookingBundle,
    *,
    viewer_user_id: UUID | None = None,
    include_all_payments: bool = False,
) -> BookingView:
    booking = bundle.booking
    participant_users = {item.id: item.user_id for item in bundle.participants}
    return BookingView(
        id=booking.id,
        lobby_id=booking.lobby_id,
        organization_id=booking.organization_id,
        organization_venue_id=booking.organization_venue_id,
        venue_space_id=booking.venue_space_id,
        status=booking.status,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
        price_cents=booking.price_cents,
        currency=booking.currency,
        seats=booking.seats,
        policy_version=booking.policy_version,
        cancellation_policy=booking.cancellation_policy,
        response_due_at=booking.response_due_at,
        payment_due_at=booking.payment_due_at,
        hold_expires_at=booking.hold_expires_at,
        accepted_at=booking.accepted_at,
        confirmed_at=booking.confirmed_at,
        cancelled_at=booking.cancelled_at,
        expired_at=booking.expired_at,
        completed_at=booking.completed_at,
        cancellation_reason=booking.cancellation_reason,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        participants=[
            ParticipantView(
                user_id=item.user_id,
                seat=item.seat,
                active=item.active,
                contribution_cents=item.contribution_cents,
                payment_status=(
                    item.payment_status
                    if include_all_payments or item.user_id == viewer_user_id
                    else "HIDDEN"
                ),
                confirmed_at=item.confirmed_at,
                declined_at=item.declined_at,
                replaced_by_user_id=item.replaced_by_user_id,
            )
            for item in bundle.participants
        ],
        timers=[
            TimerView(
                timer_type=item.timer_type,
                status=item.status,
                started_at=item.started_at,
                deadline_at=item.deadline_at,
                ended_at=item.ended_at,
            )
            for item in bundle.timers
        ],
        hold=(
            HoldView(
                id=bundle.hold.id,
                space_id=bundle.hold.venue_space_id,
                starts_at=bundle.hold.starts_at,
                ends_at=bundle.hold.ends_at,
                status=bundle.hold.status,
                released_at=bundle.hold.released_at,
            )
            if bundle.hold is not None
            else None
        ),
        payments=[
            PaymentView(
                id=item.id,
                participant_id=item.participant_id,
                version=item.version,
                amount_cents=item.amount_cents,
                status=item.status,
                paid_at=item.paid_at,
            )
            for item in bundle.payments
            if include_all_payments or participant_users.get(item.participant_id) == viewer_user_id
        ],
    )


@router.post("/bookings", response_model=BookingView, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.create(
            current.user_id,
            lobby_id=payload.lobby_id,
            organization_venue_id=payload.organization_venue_id,
            venue_space_id=payload.venue_space_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(bundle, viewer_user_id=current.user_id)


@router.get("/bookings", response_model=BookingListResponse)
def list_my_bookings(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingListResponse:
    service = BookingService(session)
    return BookingListResponse(
        bookings=[
            _view(bundle, viewer_user_id=current.user_id)
            for bundle in service.list_for_user(current.user_id)
        ]
    )


@router.get(
    "/organizations/{organization_id}/bookings",
    response_model=BookingListResponse,
)
def list_organization_bookings(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingListResponse:
    service = BookingService(session)
    try:
        bundles = service.list_for_organization(current.user_id, organization_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return BookingListResponse(
        bookings=[_view(bundle, include_all_payments=True) for bundle in bundles]
    )


@router.get("/bookings/{booking_id}", response_model=BookingView)
def get_booking(
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.get(current.user_id, booking_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return _view(
        bundle,
        viewer_user_id=current.user_id,
        include_all_payments=service.viewer_is_org(current.user_id, bundle.booking),
    )


@router.post(
    "/bookings/{booking_id}/participant-confirmation",
    response_model=BookingView,
)
def confirm_participation(
    booking_id: UUID,
    payload: ParticipantConfirmation,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.confirm_participation(
            current.user_id, booking_id, decision=payload.decision
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(bundle, viewer_user_id=current.user_id)


@router.post("/bookings/{booking_id}/substitutions", response_model=BookingView)
def substitute_participant(
    booking_id: UUID,
    payload: SubstitutionCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.substitute(
            current.user_id,
            booking_id,
            replace_user_id=payload.replace_user_id,
            new_user_id=payload.new_user_id,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(
        bundle,
        viewer_user_id=current.user_id,
        include_all_payments=service.viewer_is_org(current.user_id, bundle.booking),
    )


@router.post("/bookings/{booking_id}/payments/simulate", response_model=BookingView)
def simulate_payment(
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.simulate_payment(current.user_id, booking_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(bundle, viewer_user_id=current.user_id)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingView)
def cancel_booking(
    booking_id: UUID,
    payload: CancelRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.cancel(current.user_id, booking_id, reason=payload.reason)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(
        bundle,
        viewer_user_id=current.user_id,
        include_all_payments=service.viewer_is_org(current.user_id, bundle.booking),
    )


@router.post(
    "/organizations/{organization_id}/bookings/{booking_id}/accept",
    response_model=BookingView,
)
def accept_booking(
    organization_id: UUID,
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.accept(current.user_id, booking_id)
        if bundle.booking.organization_id != organization_id:
            raise BookingNotFound
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(bundle, include_all_payments=True)


@router.post(
    "/organizations/{organization_id}/bookings/{booking_id}/decline",
    response_model=BookingView,
)
def decline_booking(
    organization_id: UUID,
    booking_id: UUID,
    payload: CancelRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.decline(current.user_id, booking_id, reason=payload.reason)
        if bundle.booking.organization_id != organization_id:
            raise BookingNotFound
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(bundle, include_all_payments=True)


@router.post(
    "/organizations/{organization_id}/bookings/{booking_id}/cancel",
    response_model=BookingView,
)
def cancel_booking_by_venue(
    organization_id: UUID,
    booking_id: UUID,
    payload: CancelRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.cancel(
            current.user_id,
            booking_id,
            reason=payload.reason,
            by_venue=True,
        )
        if bundle.booking.organization_id != organization_id:
            raise BookingNotFound
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(bundle, include_all_payments=True)


@router.post(
    "/organizations/{organization_id}/bookings/{booking_id}/complete",
    response_model=BookingView,
)
def complete_booking(
    organization_id: UUID,
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> BookingView:
    service = BookingService(session)
    try:
        bundle = service.complete(current.user_id, booking_id)
        if bundle.booking.organization_id != organization_id:
            raise BookingNotFound
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _view(bundle, include_all_payments=True)
