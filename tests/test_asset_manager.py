import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from PIL import Image

from astrbot_plugin_nikke.asset_manager import AssetManager


class AssetManagerTests(unittest.TestCase):
    def test_game_resource_url_matches_official_cdn_path_contract(self):
        self.assertEqual(
            AssetManager.game_resource_url("icon/equip/icn_equipment_head_attacker_t9_3.webp"),
            "https://sg-tools-cdn.blablalink.com/ct-58/xq-81/f1333fe625de471b7221f89b15e48242.webp",
        )

    def test_cache_wins_and_corrupt_cache_falls_back_to_project(self):
        with tempfile.TemporaryDirectory() as td:
            cache, assets = Path(td) / "cache", Path(td) / "assets"
            for root, color in [(cache, "red"), (assets, "blue")]:
                (root / "portraits").mkdir(parents=True)
                Image.new("RGBA", (20, 20), color).save(root / "portraits/191.png")
            manager = AssetManager(cache, assets)
            self.assertEqual(manager.get_character_portrait("5004", "191").getpixel((0, 0)), (255, 0, 0, 255))
            (cache / "portraits/191.png").write_bytes(b"invalid")
            self.assertEqual(manager.get_character_portrait("5004", "191").getpixel((0, 0)), (0, 0, 255, 255))

    def test_missing_ids_and_network_errors_return_images(self):
        with tempfile.TemporaryDirectory() as td:
            manager = AssetManager(td, td, remote=True)
            with patch("astrbot_plugin_nikke.asset_manager.httpx.stream", side_effect=httpx.ConnectError("offline")) as request:
                for _ in range(2):
                    image = manager.get_character_portrait("unknown", "999999")
                    self.assertEqual(image.mode, "RGBA")
                    self.assertIsNotNone(image.getbbox())
                self.assertEqual(request.call_count, 1)
            for slot in ("head", "torso", "arm", "leg"):
                self.assertIsNotNone(manager.get_equipment_icon(slot, "../../absent").getbbox())

    def test_remote_asset_is_cached_and_reused(self):
        with tempfile.TemporaryDirectory() as td:
            buffer = io.BytesIO()
            Image.new("RGBA", (30, 50), "green").save(buffer, "PNG")
            response = httpx.Response(200, content=buffer.getvalue(), request=httpx.Request("GET", "https://example.com"))
            manager = AssetManager(td, td, remote=True)
            with patch("astrbot_plugin_nikke.asset_manager.httpx.stream") as stream:
                stream.return_value.__enter__.return_value = response
                self.assertEqual(manager.get_character_portrait("5004", "191").size, (30, 50))
                manager.get_character_portrait("5004", "191")
                self.assertEqual(stream.call_count, 1)

    def test_all_icon_fallbacks_and_invalid_sources(self):
        with tempfile.TemporaryDirectory() as td:
            manager = AssetManager(td, td)
            for method in (manager.get_favorite_item_icon, manager.get_cube_icon, manager.get_element_icon,
                           manager.get_corporation_icon, manager.get_weapon_icon, manager.get_burst_icon):
                self.assertIsNotNone(method(None).getbbox())
