# SPDX-License-Identifier: GPL-3.0-or-later

import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from astrbot_plugin_nikke.client import BlaBlaClient, BlaBlaError
from astrbot_plugin_nikke.renderer import CardRenderer
from astrbot_plugin_nikke.storage import NikkeStore
from astrbot_plugin_nikke.web_service import BindingWebService


VALID_COOKIE = "game_token=secret-token; game_uid=12345; game_openid=67890"


class BindingApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_endpoint_requires_service_key(self):
        with tempfile.TemporaryDirectory() as td:
            store = NikkeStore(td)
            service = BindingWebService(store, object(), Path(td) / "extension.zip", "service-secret")
            from aiohttp.test_utils import TestClient, TestServer

            client = TestClient(TestServer(service.app()))
            await client.start_server()
            try:
                denied = await client.post("/api/bind/session", json={"qq_id": "123456"})
                self.assertEqual(denied.status, 401)
                created = await client.post(
                    "/api/bind/session",
                    json={"qq_id": "123456"},
                    headers={"Authorization": "Bearer service-secret"},
                )
                self.assertEqual(created.status, 201)
                payload = await created.json()
                self.assertTrue(payload["ok"])
                self.assertIsNotNone(store.get_bind_session(payload["token"]))
            finally:
                await client.close()

    async def test_cookie_submission_keeps_only_blablalink_site_cookies(self):
        class CaptureClient:
            def __init__(self):
                self.cookie = ""

            async def validate_cookie(self, cookie):
                self.cookie = cookie
                from astrbot_plugin_nikke.client import ValidationResult
                return ValidationResult(True, "12345", "67890", "角色", "昵称", "3")

        with tempfile.TemporaryDirectory() as td:
            store = NikkeStore(td)
            store.create_bind_session("a" * 40, "123456", 600)
            capture = CaptureClient()
            service = BindingWebService(store, capture, Path(td) / "extension.zip")
            from aiohttp.test_utils import TestClient, TestServer

            client = TestClient(TestServer(service.app()))
            await client.start_server()
            try:
                response = await client.post(
                    "/api/bind/cookies",
                    json={
                        "token": "a" * 40,
                        "cookies": [
                            {"name": "game_token", "value": "token", "domain": ".blablalink.com"},
                            {"name": "game_uid", "value": "12345", "domain": ".blablalink.com"},
                            {"name": "game_openid", "value": "67890", "domain": ".blablalink.com"},
                            {"name": "site_session", "value": "needed", "domain": "www.blablalink.com"},
                            {"name": "foreign", "value": "secret", "domain": ".example.com"},
                        ],
                    },
                )
                self.assertEqual(response.status, 200)
                self.assertIn("site_session=needed", capture.cookie)
                self.assertNotIn("foreign=secret", capture.cookie)
            finally:
                await client.close()


class FakeClient(BlaBlaClient):
    def __init__(self, responses):
        super().__init__(5)
        self.responses = responses
        self.calls = []

    async def _post(self, path, cookie, payload):
        self.calls.append((path, cookie, payload))
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        return value


class OpenIdFallbackClient(BlaBlaClient):
    def __init__(self):
        super().__init__(5)
        self.payloads = []

    async def _post(self, path, cookie, payload):
        self.payloads.append((path, payload))
        if path == "/api/ugc/direct/standalonesite/User/GetUserGamePlayerInfo":
            if payload.get("intl_openid"):
                return {"code": 0, "data": {"area_id": 3, "role_name": "指挥官"}}
            raise BlaBlaError("MetaData no user account", "1300001")
        if path == "/api/game/proxy/Game/GetUserProfileBasicInfo":
            return {"code": 0, "data": {"basic_info": {"nickname": "测试账号"}}}
        raise AssertionError(path)


class CanonicalOpenIdClient(BlaBlaClient):
    def __init__(self):
        super().__init__(5)

    async def _post(self, path, cookie, payload):
        if path == "/api/ugc/direct/standalonesite/User/GetUserGamePlayerInfo":
            if payload.get("intl_openid") == "3-67890":
                return {"code": 0, "data": {"area_id": 3, "role_name": "指挥官"}}
            raise BlaBlaError("MetaData no user account", "1300001")
        if path == "/api/ugc/proxy/standalonesite/User/GetUserInfoNew":
            return {"code": 0, "data": {"info": {"intl_openid": "3-67890"}}}
        if path == "/api/ugc/direct/standalonesite/User/GetUserPrivacySetting":
            return {"code": 0, "data": {}}
        if path == "/api/game/proxy/Game/GetUserProfileBasicInfo":
            return {"code": 0, "data": {"basic_info": {"nickname": "正式账号"}}}
        raise AssertionError(path)


class StoreTests(unittest.TestCase):
    def test_single_use_and_encryption(self):
        with tempfile.TemporaryDirectory() as td:
            store = NikkeStore(td)
            store.create_bind_session("a" * 40, "10001", 600)
            qq_id = store.consume_bind_session(
                "a" * 40, VALID_COOKIE, "12345", "67890", "丽塔", "丽塔", "3"
            )
            self.assertEqual(qq_id, "10001")
            self.assertEqual(store.get_account("10001")["cookie"], VALID_COOKIE)
            with sqlite3.connect(Path(td) / "nikke.sqlite3") as conn:
                encrypted = conn.execute("SELECT cookie_cipher FROM accounts").fetchone()[0]
            self.assertNotIn(b"secret-token", encrypted)
            with self.assertRaises(ValueError):
                store.consume_bind_session(
                    "a" * 40, VALID_COOKIE, "12345", "67890", "丽塔", "丽塔", "3"
                )

    def test_expired_session_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            store = NikkeStore(td)
            store.create_bind_session("b" * 40, "10001", -1)
            with self.assertRaises(ValueError):
                store.consume_bind_session(
                    "b" * 40, VALID_COOKIE, "12345", "67890", "", "", "3"
                )

    def test_idempotent_run(self):
        with tempfile.TemporaryDirectory() as td:
            store = NikkeStore(td)
            self.assertTrue(store.claim_run("2026-09-05:1:daily", "1", "daily"))
            self.assertFalse(store.claim_run("2026-09-05:1:daily", "1", "daily"))


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_player_lookup_falls_back_to_game_openid(self):
        client = OpenIdFallbackClient()
        result = await client.validate_cookie(VALID_COOKIE)
        self.assertEqual(result.area_id, "3")
        self.assertEqual(result.nickname, "测试账号")
        self.assertIn(
            ("/api/ugc/direct/standalonesite/User/GetUserGamePlayerInfo", {"intl_openid": "67890"}),
            client.payloads,
        )

    async def test_player_lookup_uses_canonical_openid(self):
        client = CanonicalOpenIdClient()
        result = await client.validate_cookie(VALID_COOKIE)
        self.assertEqual(result.area_id, "3")
        self.assertEqual(result.game_openid, "3-67890")
        self.assertEqual(result.nickname, "正式账号")

    async def test_validation_and_profile(self):
        from astrbot_plugin_nikke.client import CHECK_LOGIN, PLAYER_INFO, PROFILE

        client = FakeClient(
            {
                PLAYER_INFO: {"code": 0, "data": {"area_id": 3, "role_name": "旧名称"}},
                PROFILE: {"code": 0, "data": {"basic_info": {"nickname": "新名称"}}},
                CHECK_LOGIN: {"code": 0, "data": {}},
            }
        )
        result = await client.validate_cookie(VALID_COOKIE)
        self.assertTrue(result.valid)
        self.assertEqual(result.nickname, "新名称")
        self.assertEqual(result.area_id, "3")
        self.assertTrue(all(call[1] == VALID_COOKIE for call in client.calls))

    async def test_missing_required_cookie(self):
        client = FakeClient({})
        with self.assertRaises(BlaBlaError):
            await client.validate_cookie("game_token=x; game_uid=1")

    def test_ael_formula(self):
        value = BlaBlaClient.calculate_ael({"grade": 3, "core": 2, "effects": []})
        self.assertEqual(value, round(1.1 * 1.13, 4))

    def test_ael_uses_attack_and_element_effects(self):
        value = BlaBlaClient.calculate_ael(
            {
                "grade": 0,
                "core": 0,
                "equipment_effects": [
                    {"function_type": "StatAtk", "function_value": 1190},
                    {"function_type": "IncElementDmg", "function_value": 2300},
                ],
            }
        )
        self.assertEqual(value, round((1 + 0.9 * 0.119) * (1 + 0.23 + 0.10), 4))


class RendererTests(unittest.TestCase):
    def test_summary_card(self):
        with tempfile.TemporaryDirectory() as td:
            renderer = CardRenderer(td, td)
            path = renderer.render_summary([(f"用户{i}", "签到成功") for i in range(25)])
            self.assertTrue(Path(path).exists())
            self.assertGreater(Path(path).stat().st_size, 1000)


class ExtensionTests(unittest.TestCase):
    def test_extension_permissions_are_scoped(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "extension" / "manifest.json").read_text(encoding="utf-8"))
        hosts = manifest["host_permissions"]
        self.assertNotIn("<all_urls>", hosts)
        self.assertEqual(set(manifest["permissions"]), {"cookies", "tabs", "storage"})


if __name__ == "__main__":
    unittest.main()
