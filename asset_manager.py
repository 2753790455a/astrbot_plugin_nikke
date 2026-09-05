# SPDX-License-Identifier: GPL-3.0-or-later
"""独立的图片资源缓存；任何缺图或网络错误均返回可渲染的占位素材。"""

from __future__ import annotations

import io
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageDraw


class AssetManager:
    MAX_BYTES = 12 * 1024 * 1024
    MAX_PIXELS = 20_000_000
    CDN = "https://raw.githubusercontent.com/Nikke-db/Nikke-db.github.io/main/images"

    def __init__(self, cache_dir: str | Path, asset_dir: str | Path, *, remote: bool = False):
        self.cache_dir = Path(cache_dir)
        self.asset_dir = Path(asset_dir)
        self.remote = remote
        self._failed: dict[str, float] = {}
        try:
            self.sources = json.loads((self.asset_dir / "sources.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.sources = {}
        if not isinstance(self.sources, dict):
            self.sources = {}
        try:
            self.equipment_map = json.loads((self.asset_dir / "equipment.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.equipment_map = {}
        if not isinstance(self.equipment_map, dict):
            self.equipment_map = {}

    @staticmethod
    def game_resource_url(path: str) -> str:
        """按官网资源路径合同生成CDN地址，与ExiaInvasion适配保持一致。"""
        path = path.lstrip("/")
        buckets = []
        for seed in (224737, 1000639, 2654435761, 2654435769, 1000621, 4294967291)[:path.count("/")]:
            value = seed
            for char in path:
                value = (value * 33 + ord(char)) & 0xFFFFFFFF
            signed = value if value < 0x80000000 else value - 0x100000000
            modulo = signed % seed
            buckets.append(f"{chr(97 + modulo // 26 % 26)}{chr(97 + modulo % 26)}-{modulo % 99:02d}")
        filename = hashlib.md5(path.encode("utf-8")).hexdigest() + Path(path).suffix
        return "https://sg-tools-cdn.blablalink.com/" + "/".join([*buckets, filename])

    @staticmethod
    def _key(value) -> str:
        value = str(value or "").lower()
        return value if re.fullmatch(r"[a-z0-9_-]{1,80}", value) else "missing"

    @classmethod
    def _decode(cls, content: bytes) -> Image.Image:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > cls.MAX_PIXELS:
                raise ValueError("素材像素过大")
            image.load()
            return image.convert("RGBA")

    def _load(self, kind: str, key: str, remote_url: str = "") -> Image.Image | None:
        relative = f"{kind}/{self._key(key)}.png"
        for base in (self.cache_dir, self.asset_dir):
            try:
                path = base / relative
                if path.stat().st_size <= self.MAX_BYTES:
                    return self._decode(path.read_bytes())
            except (OSError, ValueError, Image.DecompressionBombError):
                pass
        url = self.sources.get(relative, remote_url)
        if not self.remote or not isinstance(url, str) or not url.startswith("https://"):
            return None
        if self._failed.get(relative, 0) > time.monotonic():
            return None
        try:
            # 公共素材请求不携带账号Cookie；限制总下载时长和响应大小。
            started = time.monotonic()
            content = bytearray()
            with httpx.stream("GET", url, timeout=3, follow_redirects=True) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > self.MAX_BYTES or time.monotonic() - started > 6:
                        raise ValueError("素材下载超过限制")
            image = self._decode(bytes(content))
            try:
                destination = self.cache_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(f".{uuid.uuid4().hex}.tmp")
                try:
                    image.save(temporary, format="PNG")
                    temporary.replace(destination)
                finally:
                    temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return image
        except (httpx.HTTPError, OSError, ValueError, Image.DecompressionBombError):
            self._failed[relative] = time.monotonic() + 300
            return None

    @staticmethod
    def fallback(kind: str) -> Image.Image:
        if kind == "portrait":
            image = Image.new("RGBA", (600, 900))
            draw = ImageDraw.Draw(image)
            color = (164, 178, 205, 75)
            draw.ellipse((213, 66, 385, 244), fill=color)
            draw.polygon([(245, 224), (351, 224), (454, 340), (403, 560),
                          (470, 850), (332, 900), (300, 616), (269, 900),
                          (133, 850), (197, 560), (146, 340)], fill=color)
            return image
        image = Image.new("RGBA", (128, 128))
        draw = ImageDraw.Draw(image)
        color = (180, 199, 220, 220)
        shapes = {
            "head": [(30, 75), (30, 43), (48, 23), (80, 23), (98, 43), (98, 75), (83, 87), (83, 58), (45, 58), (45, 87)],
            "torso": [(41, 24), (52, 35), (76, 35), (87, 24), (109, 48), (92, 64), (85, 103), (43, 103), (36, 64), (19, 48)],
            "arm": [(31, 28), (53, 25), (63, 67), (80, 53), (98, 65), (78, 99), (44, 101)],
            "leg": [(36, 23), (88, 23), (96, 99), (72, 99), (62, 55), (54, 99), (30, 99)],
            "cube": [(64, 20), (108, 44), (108, 87), (64, 110), (20, 87), (20, 44)],
        }
        draw.polygon(shapes.get(kind, [(64, 18), (107, 64), (64, 110), (21, 64)]), outline=color, width=5)
        if kind == "cube":
            draw.line([(20, 44), (64, 67), (108, 44)], fill=color, width=4)
            draw.line([(64, 67), (64, 110)], fill=color, width=4)
        return image

    def get_character_portrait(self, name_code, resource_id) -> Image.Image:
        # 项目可用name_code补充特例，通用远端则使用明确的resource_id。
        image = self._load("portraits", str(name_code))
        if image is None:
            rid = self._key(resource_id)
            url = f"{self.CDN}/FB/c{rid.zfill(3)}_00.png" if rid.isdigit() else ""
            image = self._load("portraits", rid, url)
        return image if image is not None else self.fallback("portrait")

    def get_equipment_icon(self, slot, equipment_id) -> Image.Image:
        resource = self.equipment_map.get(str(equipment_id), "")
        url = self.game_resource_url(f"icon/equip/{resource}.webp") if resource and self._key(resource) != "missing" else ""
        image = self._load("equipment", str(equipment_id), url) if equipment_id else None
        if image is None:
            image = self._load("slots", slot)
        return image if image is not None else self.fallback(slot)

    def _icon(self, kind, key, fallback, url="") -> Image.Image:
        image = self._load(kind, self._key(key), url)
        return image if image is not None else self.fallback(fallback)

    def get_favorite_item_icon(self, tid):
        return self._icon("favorite", tid, "favorite")

    def get_cube_icon(self, tid):
        return self._icon("cube", tid, "cube")

    def get_element_icon(self, element):
        key = self._key(element)
        key = "electronic" if key == "electric" else key
        url = f"https://www.blablalink.com/assets/nikke/version/default/shiftysassets/images/icon-code-{key}.png" if key in {"fire", "water", "wind", "iron", "electronic"} else ""
        return self._icon("element", element, "element", url)

    def get_corporation_icon(self, corporation):
        key = self._key(corporation)
        slug = "tetraline" if key == "tetra" else key
        url = f"{self.CDN}/manufacturer/icn_corp_{slug}.png" if key in {"tetra", "elysion", "missilis", "pilgrim"} else ""
        return self._icon("corporation", key, "corporation", url)

    def get_weapon_icon(self, weapon):
        key = self._key(weapon)
        url = f"{self.CDN}/gun/icn_weapon_{key}.png" if key in {"ar", "mg", "rl", "sg", "smg", "sr"} else ""
        return self._icon("weapon", key, "weapon", url)

    def get_burst_icon(self, burst):
        key = self._key(burst)
        resource = "icn_burst_all" if key == "allstep" else (f"icn_burst_0{key[-1]}" if key in {"step1", "step2", "step3"} else "")
        url = self.game_resource_url(f"icon/atlas_common_class/{resource}.webp") if resource else ""
        return self._icon("burst", key, "burst", url)
