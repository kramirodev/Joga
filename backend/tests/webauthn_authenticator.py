"""Autenticador WebAuthn sintético para testes (P-256, atestação none)."""

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.modules.identity.encoding import b64url_decode, b64url_encode


@dataclass
class SoftAuthenticator:
    """Gera respostas WebAuthn válidas sem hardware nem rede."""

    rp_id: str
    origin: str
    user_handle: bytes
    credential_id: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    sign_count: int = 0
    private_key: ec.EllipticCurvePrivateKey = field(
        default_factory=lambda: ec.generate_private_key(ec.SECP256R1())
    )

    def registration_credential(self, challenge_b64: str) -> dict[str, Any]:
        challenge = b64url_decode(challenge_b64)
        client_data = {
            "type": "webauthn.create",
            "challenge": b64url_encode(challenge),
            "origin": self.origin,
            "crossOrigin": False,
        }
        client_data_json = _client_data_json(client_data)
        rp_id_hash = hashlib.sha256(self.rp_id.encode()).digest()
        flags = 0x45  # user present + user verified + attested credential data
        auth_data = rp_id_hash + bytes([flags]) + self.sign_count.to_bytes(4, "big") + b"\x00" * 16
        public_numbers = self.private_key.public_key().public_numbers()
        cose_key = cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: public_numbers.x.to_bytes(32, "big"),
                -3: public_numbers.y.to_bytes(32, "big"),
            }
        )
        auth_data += len(self.credential_id).to_bytes(2, "big") + self.credential_id + cose_key
        attestation_object = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64url_encode(self.credential_id),
            "rawId": b64url_encode(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url_encode(client_data_json),
                "attestationObject": b64url_encode(attestation_object),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def authentication_credential(
        self,
        challenge_b64: str,
        *,
        sign_count: int | None = None,
    ) -> dict[str, Any]:
        challenge = b64url_decode(challenge_b64)
        client_data = {
            "type": "webauthn.get",
            "challenge": b64url_encode(challenge),
            "origin": self.origin,
            "crossOrigin": False,
        }
        client_data_json = _client_data_json(client_data)
        new_count = self.sign_count + 1 if sign_count is None else sign_count
        rp_id_hash = hashlib.sha256(self.rp_id.encode()).digest()
        auth_data = rp_id_hash + bytes([0x05]) + new_count.to_bytes(4, "big")
        signature = self.private_key.sign(
            auth_data + hashlib.sha256(client_data_json).digest(),
            ec.ECDSA(hashes.SHA256()),
        )
        self.sign_count = new_count
        return {
            "id": b64url_encode(self.credential_id),
            "rawId": b64url_encode(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url_encode(client_data_json),
                "authenticatorData": b64url_encode(auth_data),
                "signature": b64url_encode(signature),
                "userHandle": b64url_encode(self.user_handle),
            },
            "clientExtensionResults": {},
        }


def _client_data_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()
