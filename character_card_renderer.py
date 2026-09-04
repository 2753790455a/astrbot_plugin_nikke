# SPDX-License-Identifier: GPL-3.0-or-later
"""手机 QQ 优先的 1200×1500 单角色练度卡。"""

from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from .card_models import CharacterCardData, EquipmentData, EquipmentOption
from .renderer import CardRenderer


class CharacterCardRenderer(CardRenderer):
    WIDTH = 1200
    HEIGHT = 1500

    ELEMENT_NAMES = {
        "fire": "燃烧",
        "water": "水冷",
        "wind": "风压",
        "electric": "电击",
        "iron": "铁甲",
    }
    CORPORATION_NAMES = {
        "elysion": "极乐净土",
        "missilis": "米西利斯",
        "tetra": "泰特拉",
        "pilgrim": "朝圣者",
        "abnormal": "反常",
    }
    BURST_NAMES = {
        "step1": "BURST I",
        "step2": "BURST II",
        "step3": "BURST III",
        "allstep": "BURST 全阶段",
    }
    SLOT_NAMES = {
        "head": "HEAD · 头部",
        "torso": "TORSO · 躯干",
        "arm": "ARM · 手臂",
        "leg": "LEG · 腿部",
    }

    @staticmethod
    def _number(value: int | None) -> str:
        return "—" if value is None else f"{value:,}"

    @staticmethod
    def _item_text(item) -> str:
        if item is None:
            return "未装备"
        name = item.display_name or "已装备"
        return f"{name} · Lv.{item.level}" if item.level is not None else name

    @staticmethod
    def _option_value(option: EquipmentOption) -> str:
        if option.unit == "percent":
            return f"{option.value * 100:.2f}%"
        if option.unit == "flat":
            return f"{round(option.value):,}"
        return "待确认"

    def _label(self, value, mapping: dict[str, str]) -> str:
        text = str(value or "—")
        return mapping.get(text.casefold(), text)

    def _panel(self, draw: ImageDraw.ImageDraw, box, title: str) -> None:
        draw.rounded_rectangle(box, 18, fill="#171d27", outline="#354052", width=2)
        x1, y1, _, _ = box
        draw.rectangle((x1, y1, x1 + 9, box[3]), fill="#f4b72e")
        draw.text((x1 + 30, y1 + 16), title, font=self.font(26, True), fill="#f6c85d")

    def _equipment_panel(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        item: EquipmentData,
    ) -> None:
        box = (44, y, 1156, y + 108)
        draw.rounded_rectangle(box, 16, fill="#171d27", outline="#354052", width=2)
        draw.rectangle((44, y, 53, y + 108), fill="#ea5d48")
        draw.text((74, y + 14), self.SLOT_NAMES[item.slot], font=self.font(25, True), fill="#ffffff")
        status = "未装备"
        if item.equipped:
            status = "已装备" + (f" · Lv.{item.level}" if item.level is not None else "")
        draw.text((74, y + 58), status, font=self.font(24), fill="#9fabbc")

        options = item.options[:3]
        if not options:
            draw.text((390, y + 39), "无词条", font=self.font(24), fill="#778294")
            return
        line_y = y + 10
        for option in options:
            level = f"  L{option.level}" if option.level is not None else ""
            value = self._option_value(option)
            draw.text(
                (390, line_y),
                f"{option.display_name}{level}",
                font=self.font(24),
                fill="#e8edf5" if option.unit != "unknown" else "#aab3c1",
            )
            draw.text((1020, line_y), value, font=self.font(24, True), fill="#65cbe8", anchor="ra")
            line_y += 31

    def render_character(self, data: CharacterCardData) -> str:
        canvas = Image.new("RGB", (self.WIDTH, self.HEIGHT), "#0e1219")
        draw = ImageDraw.Draw(canvas)
        for y in range(self.HEIGHT):
            ratio = y / (self.HEIGHT - 1)
            draw.line(
                (0, y, self.WIDTH, y),
                fill=(14 + int(10 * ratio), 18 + int(12 * ratio), 25 + int(18 * ratio)),
            )

        draw.polygon([(0, 0), (730, 0), (590, 190), (0, 190)], fill="#f2b229")
        draw.polygon([(850, 0), (1200, 0), (1200, 76), (805, 76)], fill="#eb5b47")
        draw.text((48, 24), "NIKKE · CHARACTER", font=self.font(27, True), fill="#17191f")
        draw.text((48, 67), data.name_cn, font=self.font(52, True), fill="#11151c")
        draw.text((50, 132), data.name_en or data.name_code, font=self.font(28), fill="#343946")
        draw.text((825, 102), f"Lv.{data.level:,}", font=self.font(46, True), fill="#ffffff")

        metadata = " · ".join(
            [
                str(data.rarity or "—"),
                self._label(data.element, self.ELEMENT_NAMES),
                str(data.weapon or "—"),
                self._label(data.burst, self.BURST_NAMES),
                self._label(data.corporation, self.CORPORATION_NAMES),
            ]
        )
        draw.text((52, 202), metadata, font=self.font(25, True), fill="#d9e0ea")

        self._panel(draw, (44, 250, 1156, 342), "角色身份")
        identity = (
            f"CODE {data.name_code}    RESOURCE {data.resource_id or '—'}    "
            f"突破 {'★' * min(3, max(0, data.grade)) or '未突破'}    核心 +{data.core}"
        )
        draw.text((238, 270), identity, font=self.font(25), fill="#edf1f7")

        self._panel(draw, (44, 360, 1156, 495), "基础属性")
        stats = [
            ("战斗力", self._number(data.combat)),
            ("HP", self._number(data.hp)),
            ("攻击", self._number(data.attack)),
            ("防御", self._number(data.defense)),
        ]
        for index, (label, value) in enumerate(stats):
            x = 225 + index * 225
            draw.text((x, 386), label, font=self.font(24), fill="#909bad", anchor="ma")
            draw.text((x, 438), value, font=self.font(30, True), fill="#ffffff", anchor="ma")

        self._panel(draw, (44, 514, 1156, 710), "养成信息")
        growth = [
            ("技能", f"{data.skill1_level} / {data.skill2_level} / {data.burst_skill_level}"),
            ("突破", "★" * min(3, max(0, data.grade)) or "未突破"),
            ("核心", f"+{data.core}"),
            ("好感度", f"Lv.{data.bond_level}" if data.bond_level is not None else "—"),
            ("收藏品", self._item_text(data.favorite_item)),
            ("魔方", self._item_text(data.cube)),
        ]
        for index, (label, value) in enumerate(growth):
            column = index % 3
            row = index // 3
            x1 = 210 + column * 310
            y1 = 550 + row * 76
            draw.text((x1, y1), label, font=self.font(24), fill="#919daf", anchor="ma")
            draw.text((x1, y1 + 37), value, font=self.font(27, True), fill="#f2f5f9", anchor="ma")

        draw.text((48, 734), "四件装备", font=self.font(28, True), fill="#f6c85d")
        for index, slot in enumerate(("head", "torso", "arm", "leg")):
            self._equipment_panel(draw, 772 + index * 118, data.equipment[slot])

        self._panel(draw, (44, 1254, 1156, 1418), "装备词条汇总")
        if not data.option_totals:
            draw.text((238, 1320), "暂无已确认单位的装备词条", font=self.font(24), fill="#8d98a8")
        else:
            for index, summary in enumerate(data.option_totals[:4]):
                column = index % 2
                row = index // 2
                label_x = 180 + column * 550
                value_x = 550 + column * 550
                y = 1300 + row * 55
                value = (
                    f"{summary.value * 100:.2f}%"
                    if summary.unit == "percent"
                    else f"{round(summary.value):,}"
                )
                draw.text((label_x, y), summary.display_name, font=self.font(24), fill="#d9e0ea")
                draw.text((value_x, y), value, font=self.font(26, True), fill="#65cbe8", anchor="ra")

        footer = f"{data.commander_name} · {data.fetched_at} · v{data.plugin_version} · BlaBlaLink"
        draw.text((50, 1460), footer, font=self.font(24), fill="#7f8999")
        path = Path(self.output_dir) / f"character-{uuid.uuid4().hex}.png"
        canvas.save(path, "PNG", optimize=True)
        return str(path)
