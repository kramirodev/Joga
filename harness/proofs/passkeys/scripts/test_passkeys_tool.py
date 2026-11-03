"""Testes da ferramenta de associação de passkeys (sem rede externa)."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import passkeys_tool as tool

FINGERPRINT = "FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C"
PACKAGE = "com.anonymous.joga"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


class PasskeysToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        tool.write_assetlinks(
            PACKAGE,
            [FINGERPRINT],
            Path(cls.directory.name) / ".well-known" / "assetlinks.json",
        )
        handler = partial(QuietHandler, directory=cls.directory.name)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.directory.cleanup()

    def test_normalize_accepts_colons_and_plain_hex(self) -> None:
        plain = FINGERPRINT.replace(":", "").lower()
        self.assertEqual(tool.normalize_fingerprint(FINGERPRINT), FINGERPRINT)
        self.assertEqual(tool.normalize_fingerprint(plain), FINGERPRINT)

    def test_normalize_rejects_wrong_length(self) -> None:
        with self.assertRaises(ValueError):
            tool.normalize_fingerprint("AA:BB")

    def test_build_statement_uses_login_relation(self) -> None:
        statement = tool.build_statement(PACKAGE, [FINGERPRINT])[0]
        self.assertEqual(statement["relation"], [tool.RELATION])
        target = statement["target"]
        self.assertEqual(target["namespace"], "android_app")
        self.assertEqual(target["package_name"], PACKAGE)
        self.assertEqual(target["sha256_cert_fingerprints"], [FINGERPRINT])

    def test_build_statement_can_add_app_links_relation(self) -> None:
        statement = tool.build_statement(
            PACKAGE, [FINGERPRINT], include_app_links=True
        )[0]
        self.assertEqual(
            statement["relation"], [tool.RELATION, tool.APP_LINKS_RELATION]
        )

    def test_write_assetlinks_is_valid_json_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = tool.write_assetlinks(
                PACKAGE, [FINGERPRINT], Path(directory) / "assetlinks.json"
            )
            data = json.loads(destination.read_text(encoding="utf-8"))
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["target"]["package_name"], PACKAGE)

    def test_verify_accepts_served_file(self) -> None:
        problems = tool.verify(
            self.origin, PACKAGE, expected_fingerprint=FINGERPRINT, check_google=False
        )
        self.assertEqual(problems, [])

    def test_verify_rejects_package_mismatch(self) -> None:
        problems = tool.verify(self.origin, "com.example.outro", check_google=False)
        self.assertTrue(any("nenhuma declaração" in problem for problem in problems))

    def test_verify_rejects_fingerprint_mismatch(self) -> None:
        other = "AA" * 32
        problems = tool.verify(
            self.origin, PACKAGE, expected_fingerprint=other, check_google=False
        )
        self.assertTrue(any("não está declarada" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
