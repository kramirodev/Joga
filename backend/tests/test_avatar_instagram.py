"""Testes da importação temporária do Instagram, sem rede real (Onda 1.7)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.avatar.instagram import (
    PAGE_MAX_BYTES,
    HttpResponse,
    InstagramImageTooLarge,
    InstagramImporter,
    InstagramProfileNotFound,
    InstagramProfilePrivate,
    InstagramUnavailable,
    InvalidInstagramImage,
    InvalidInstagramUrl,
    parse_profile_url,
)
from app.modules.avatar.models import UserAvatar
from app.modules.avatar.service import (
    delete_instagram_avatar,
    import_instagram_avatar,
)
from app.modules.identity.models import AuditLog, User
from app.modules.venues.storage import LocalPhotoStorage, PhotoNotFound
from tests.settings_helpers import demo_settings, production_settings

PAGE_URL = "https://www.instagram.com/alice/"
IMAGE_URL = "https://scontent.cdninstagram.com/v/t51.2885-19/photo.jpg"
PUBLIC_IP = "93.184.216.34"


def image_bytes(
    *,
    image_format: str = "PNG",
    size: tuple[int, int] = (900, 600),
    exif: Image.Exif | None = None,
) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", size, (20, 120, 200))
    if exif is None:
        image.save(output, format=image_format)
    else:
        image.save(output, format=image_format, exif=exif)
    return output.getvalue()


def page_html(image_url: str | None, extra: str = "") -> bytes:
    meta = f'<meta property="og:image" content="{image_url}"/>' if image_url is not None else ""
    return f"<html><head>{meta}</head><body>{extra}</body></html>".encode()


class FakeTransport:
    def __init__(self, responses: Mapping[str, HttpResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[str] = []

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_bytes: int,
    ) -> HttpResponse:
        self.calls.append(url)
        response = self.responses.get(url)
        if response is None:
            raise InstagramUnavailable("sem resposta fake")
        return response


def resolver(_host: str) -> list[str]:
    return [PUBLIC_IP]


def build_importer(transport: FakeTransport) -> InstagramImporter:
    return InstagramImporter(transport=transport, resolver=resolver)


class StaticImporter:
    def __init__(self, photo) -> None:  # noqa: ANN001
        self.photo = photo
        self.calls: list[str] = []

    def fetch(self, raw_url: str):  # noqa: ANN201
        self.calls.append(raw_url)
        return self.photo


def test_parse_profile_url_accepts_only_canonical_profile() -> None:
    parsed = parse_profile_url("https://instagram.com/alice/")
    assert parsed.username == "alice"
    assert parsed.page_url == PAGE_URL

    for invalid in (
        "http://instagram.com/alice/",
        "https://evil.example/alice/",
        "https://www.instagram.com/",
        "https://www.instagram.com/alice/extra",
        "https://www.instagram.com/alice/?next=x",
        "https://user:pass@www.instagram.com/alice/",
        "https://www.instagram.com/alice:8443/",
        "https://www.instagram.com/a b/",
        "https://www.instagram.com/" + "a" * 31,
    ):
        with pytest.raises(InvalidInstagramUrl):
            parse_profile_url(invalid)


def test_valid_profile_is_downloaded_and_reencoded() -> None:
    exif = Image.Exif()
    exif[271] = "Camera de teste"
    transport = FakeTransport(
        {
            PAGE_URL: HttpResponse(200, {}, page_html(IMAGE_URL)),
            IMAGE_URL: HttpResponse(200, {"content-type": "image/png"}, image_bytes(exif=exif)),
        }
    )

    photo = build_importer(transport).fetch("https://instagram.com/alice")

    assert photo.username == "alice"
    assert photo.page_url == PAGE_URL
    assert photo.content_type == "image/jpeg"
    assert (photo.width, photo.height) == (512, 512)
    assert transport.calls == [PAGE_URL, IMAGE_URL]
    with Image.open(BytesIO(photo.data)) as result:
        assert result.format == "JPEG"
        assert result.size == (512, 512)
        assert not result.getexif()
    assert b"Camera de teste" not in photo.data


def test_http_url_and_foreign_host_are_rejected_without_request() -> None:
    transport = FakeTransport({})
    importer = build_importer(transport)

    with pytest.raises(InvalidInstagramUrl):
        importer.fetch("http://www.instagram.com/alice/")
    with pytest.raises(InvalidInstagramUrl):
        importer.fetch("https://www.instagram.com.evil.example/alice/")
    assert transport.calls == []


def test_redirect_to_internal_or_foreign_host_is_blocked() -> None:
    for location in (
        "http://127.0.0.1/internal",
        "https://169.254.169.254/latest/meta-data",
        "https://evil.example/alice/",
    ):
        transport = FakeTransport({PAGE_URL: HttpResponse(302, {"location": location}, b"")})
        with pytest.raises(InstagramUnavailable):
            build_importer(transport).fetch(PAGE_URL)
        assert transport.calls == [PAGE_URL]


def test_private_profile_returns_specific_error() -> None:
    transport = FakeTransport(
        {PAGE_URL: HttpResponse(200, {}, page_html(IMAGE_URL, '"is_private":true'))}
    )
    with pytest.raises(InstagramProfilePrivate):
        build_importer(transport).fetch(PAGE_URL)
    assert transport.calls == [PAGE_URL]


def test_missing_profile_returns_not_found() -> None:
    transport = FakeTransport(
        {PAGE_URL: HttpResponse(200, {}, page_html(None, "Sorry, this page isn't available."))}
    )
    with pytest.raises(InstagramProfileNotFound):
        build_importer(transport).fetch(PAGE_URL)


def test_login_wall_and_missing_og_image_are_unavailable() -> None:
    for html in (
        page_html(None, '<a href="/accounts/login/">Entrar</a>'),
        page_html(None),
    ):
        transport = FakeTransport({PAGE_URL: HttpResponse(200, {}, html)})
        with pytest.raises(InstagramUnavailable):
            build_importer(transport).fetch(PAGE_URL)


def test_profile_pic_url_hd_is_used_as_fallback() -> None:
    escaped = IMAGE_URL.replace("/", "\\/")
    html = page_html(
        None,
        f'<script>{{"profile_pic_url_hd":"{escaped}"}}</script>',
    )
    transport = FakeTransport(
        {
            PAGE_URL: HttpResponse(200, {}, html),
            IMAGE_URL: HttpResponse(200, {}, image_bytes()),
        }
    )
    photo = build_importer(transport).fetch(PAGE_URL)
    assert photo.username == "alice"


def test_image_larger_than_limit_is_rejected_as_413() -> None:
    oversized = b"\xff\xd8\xff" + b"0" * (5_000_000)
    transport = FakeTransport(
        {
            PAGE_URL: HttpResponse(200, {}, page_html(IMAGE_URL)),
            IMAGE_URL: HttpResponse(200, {}, oversized),
        }
    )
    with pytest.raises(InstagramImageTooLarge):
        build_importer(transport).fetch(PAGE_URL)


def test_polyglot_and_arbitrary_image_host_are_rejected() -> None:
    transport = FakeTransport(
        {
            PAGE_URL: HttpResponse(200, {}, page_html(IMAGE_URL)),
            IMAGE_URL: HttpResponse(200, {}, b"\x89PNG\r\n\x1a\n<?php echo 'x'; ?>"),
        }
    )
    with pytest.raises(InvalidInstagramImage):
        build_importer(transport).fetch(PAGE_URL)

    foreign = FakeTransport(
        {PAGE_URL: HttpResponse(200, {}, page_html("https://evil.example/photo.jpg"))}
    )
    with pytest.raises(InstagramUnavailable):
        build_importer(foreign).fetch(PAGE_URL)
    assert foreign.calls == [PAGE_URL]


def test_private_dns_resolution_is_blocked_before_request() -> None:
    transport = FakeTransport({PAGE_URL: HttpResponse(200, {}, page_html(IMAGE_URL))})
    importer = InstagramImporter(transport=transport, resolver=lambda _host: ["10.0.0.7"])
    with pytest.raises(InstagramUnavailable):
        importer.fetch(PAGE_URL)
    assert transport.calls == []


def test_page_above_limit_is_unavailable() -> None:
    transport = FakeTransport({PAGE_URL: HttpResponse(200, {}, b"x" * (PAGE_MAX_BYTES + 1))})
    with pytest.raises(InstagramUnavailable):
        build_importer(transport).fetch(PAGE_URL)


def test_scrape_requires_local_or_demo() -> None:
    with pytest.raises(ValidationError):
        production_settings(instagram_import_mode="scrape")
    assert demo_settings(instagram_import_mode="scrape").instagram_import_mode == "scrape"
    local = Settings(_env_file=None, environment="test", instagram_import_mode="scrape")
    assert local.instagram_import_mode == "scrape"
    assert (
        Settings(
            _env_file=None, environment="test", instagram_import_mode="off"
        ).instagram_import_mode
        == "off"
    )


def make_user(session: Session) -> uuid.UUID:
    user = User(status="active")
    session.add(user)
    session.flush()
    return user.id


def static_photo(data: bytes | None = None):  # noqa: ANN201
    from app.modules.avatar.instagram import InstagramPhoto
    from app.modules.avatar.photos import process_avatar

    processed = process_avatar(data or image_bytes(), max_bytes=5_000_000)
    return InstagramPhoto(
        username="alice",
        page_url=PAGE_URL,
        data=processed.data,
        content_type=processed.content_type,
        width=processed.width,
        height=processed.height,
    )


def test_service_persists_private_file_and_replaces_without_leaking(
    db_session: Session, tmp_path
) -> None:
    storage = LocalPhotoStorage(tmp_path)
    user_id = make_user(db_session)
    importer = StaticImporter(static_photo(image_bytes(size=(900, 600))))

    view = import_instagram_avatar(
        db_session,
        user_id=user_id,
        url=PAGE_URL,
        importer=importer,  # type: ignore[arg-type]
        storage=storage,
        ip_key="ip-hash",
    )
    db_session.commit()

    assert view.source == "instagram_scrape"
    assert view.source_url == PAGE_URL
    assert (view.width, view.height) == (512, 512)
    assert view.storage_key is not None
    first_key = view.storage_key
    assert storage.read(first_key)

    second = import_instagram_avatar(
        db_session,
        user_id=user_id,
        url=PAGE_URL,
        importer=StaticImporter(static_photo(image_bytes(size=(700, 700)))),  # type: ignore[arg-type]
        storage=storage,
        ip_key="ip-hash",
    )
    db_session.commit()

    assert second.storage_key is not None and second.storage_key != first_key
    with pytest.raises(PhotoNotFound):
        storage.read(first_key)
    assert db_session.scalar(select(UserAvatar).where(UserAvatar.user_id == user_id))
    audits = db_session.scalars(select(AuditLog)).all()
    assert len(audits) == 2


def test_service_delete_removes_row_and_file(db_session: Session, tmp_path) -> None:
    storage = LocalPhotoStorage(tmp_path)
    user_id = make_user(db_session)
    view = import_instagram_avatar(
        db_session,
        user_id=user_id,
        url=PAGE_URL,
        importer=StaticImporter(static_photo()),  # type: ignore[arg-type]
        storage=storage,
        ip_key=None,
    )
    db_session.commit()
    assert view.storage_key is not None

    assert delete_instagram_avatar(db_session, user_id=user_id, storage=storage)
    db_session.commit()

    assert db_session.get(UserAvatar, user_id) is None
    with pytest.raises(PhotoNotFound):
        storage.read(view.storage_key)
    assert not delete_instagram_avatar(db_session, user_id=user_id, storage=storage)
