# SPDX-License-Identifier: GPL-3.0-or-later
"""轻量 NIKKE 风格图片卡渲染。"""

from __future__ import annotations

import textwrap
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


class CardRenderer:
    WIDTH = 1200

    def __init__(self, output_dir: str | Path, font_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        font_dir = Path(font_dir)
        regular = font_dir / "NotoSansHans-Regular.otf"
        medium = font_dir / "NotoSansHans-Medium.otf"
        self.regular_path = str(regular if regular.exists() else "DejaVuSans.ttf")
        self.medium_path = str(medium if medium.exists() else self.regular_path)

    def font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.medium_path if bold else self.regular_path, size)

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        result: list[str] = []
        for paragraph in str(text).splitlines() or [""]:
            result.extend(textwrap.wrap(paragraph, width=width, break_long_words=True) or [""])
        return result

    def render(self, title: str, subtitle: str, rows: Iterable[tuple[str, str]], footer: str = "") -> str:
        normalized = [(str(k), str(v)) for k, v in rows]
        wrapped = [(k, self._wrap(v, 34)) for k, v in normalized]
        height = max(420, 250 + sum(max(1, len(lines)) * 48 + 24 for _, lines in wrapped) + 95)
        canvas = Image.new("RGB", (self.WIDTH, height), "#10131a")
        draw = ImageDraw.Draw(canvas)
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = (16 + int(10 * ratio), 19 + int(11 * ratio), 26 + int(18 * ratio))
            draw.line((0, y, self.WIDTH, y), fill=color)
        draw.polygon([(0, 0), (520, 0), (390, 172), (0, 172)], fill="#f2b229")
        draw.polygon([(820, 0), (1200, 0), (1200, 74), (770, 74)], fill="#ee5b45")
        draw.text((52, 38), "NIKKE", font=self.font(33, True), fill="#16181e")
        draw.text((52, 95), title, font=self.font(48, True), fill="#ffffff")
        draw.text((520, 112), subtitle, font=self.font(25), fill="#aeb7c6")
        y = 205
        for index, (label, lines) in enumerate(wrapped):
            block_h = max(1, len(lines)) * 48 + 18
            fill = "#191f2a" if index % 2 == 0 else "#171c25"
            draw.rounded_rectangle((44, y, 1156, y + block_h), 14, fill=fill, outline="#303949", width=2)
            draw.rectangle((44, y, 52, y + block_h), fill="#f2b229")
            draw.text((78, y + 17), label, font=self.font(27, True), fill="#f6c857")
            line_y = y + 17
            for line in lines:
                draw.text((350, line_y), line, font=self.font(27), fill="#edf1f7")
                line_y += 48
            y += block_h + 20
        stamp = footer or f"数据时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ·  来源 BlaBlaLink"
        draw.text((50, height - 58), stamp, font=self.font(21), fill="#7f8999")
        path = self.output_dir / f"card-{uuid.uuid4().hex}.png"
        canvas.save(path, "PNG", optimize=True)
        return str(path)

    def render_roster(self, nickname: str, characters: list[dict], name_map: dict[str, str]) -> str:
        sorted_chars = sorted(
            characters,
            key=lambda item: (int(item.get("combat", 0) or 0), int(item.get("lv", 0) or 0)),
            reverse=True,
        )
        rows = []
        for item in sorted_chars[:20]:
            code = str(item.get("name_code", ""))
            name = name_map.get(code, code or "未知妮姬")
            grade = int(item.get("grade", 0) or 0)
            core = int(item.get("core", 0) or 0)
            rows.append(
                (
                    name,
                    f"Lv.{item.get('lv', 1)}  战力 {item.get('combat', 0)}  技能 "
                    f"{item.get('skill1_lv', 1)}/{item.get('skill2_lv', 1)}/{item.get('ulti_skill_lv', 1)}  "
                    f"突破 {grade}  核心 {core}",
                )
            )
        subtitle = f"{nickname} · 共 {len(characters)} 名 · 按战力排序"
        return self.render("妮姬练度一览", subtitle, rows or [("暂无数据", "未获取到角色信息")])

    def render_summary(self, rows: list[tuple[str, str]]) -> str:
        return self.render("每日任务汇总", f"参与账号 {len(rows)} 个", rows or [("暂无账号", "尚未有人启用推送")])

