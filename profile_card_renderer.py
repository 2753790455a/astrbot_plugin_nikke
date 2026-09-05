# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile dashboard image renderer."""

from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from .profile_models import ProfileDashboardData
from .renderer import CardRenderer


PROFILE_THEME = {
    "header": "#0B1118",
    "background": "#0E141B",
    "panel": "#151D26",
    "panel_alt": "#192430",
    "primary": "#29A7E8",
    "secondary": "#70D6FF",
    "text": "#F3F7FA",
    "muted": "#8FA0AF",
    "border": "#263646",
}


class ProfileCardRenderer(CardRenderer):
    WIDTH = 1200

    def _text(self, draw, xy, text, size, color, *, width=None, bold=False):
        text = str(text).replace("\n", " ")
        font = self.font(size, bold)
        while width and draw.textlength(text, font=font) > width and size > 12:
            size -= 1
            font = self.font(size, bold)
        if width and draw.textlength(text, font=font) > width:
            while text and draw.textlength(text + "\u2026", font=font) > width:
                text = text[:-1]
            text += "\u2026"
        draw.text(xy, text, font=font, fill=color, anchor="lt")

    def _text_right(self, draw, xy, text, size, color, *, width=None, bold=False):
        text = str(text).replace("\n", " ")
        font = self.font(size, bold)
        while width and draw.textlength(text, font=font) > width and size > 12:
            size -= 1
            font = self.font(size, bold)
        if width and draw.textlength(text, font=font) > width:
            while text and draw.textlength(text + "\u2026", font=font) > width:
                text = text[:-1]
            text += "\u2026"
        draw.text(xy, text, font=font, fill=color, anchor="rt")

    def _section_panel(self, draw, box, title, *, fill=None):
        x, y, w, h = box
        fill = fill or PROFILE_THEME["panel"]
        draw.rounded_rectangle(box, 14, fill=fill, outline=PROFILE_THEME["border"], width=1)
        draw.line((x + 22, y + 25, x + 50, y + 25), fill=PROFILE_THEME["primary"], width=3)
        self._text(draw, (x + 60, y + 16), title, 20, PROFILE_THEME["muted"])

    @staticmethod
    def _number(value) -> str:
        return "\u2014" if value is None else f"{value:,}"

    def render_profile(self, data: ProfileDashboardData) -> str:
        theme = PROFILE_THEME
        sections = self._collect_sections(data)
        header_h = 140
        panel_gap = 20
        footer_h = 60
        content_h = sum(h for _, h in sections) + (len(sections) - 1) * panel_gap
        total_h = header_h + content_h + footer_h + 40

        canvas = Image.new("RGB", (self.WIDTH, total_h), theme["background"])
        draw = ImageDraw.Draw(canvas)

        # Header
        draw.rectangle((0, 0, self.WIDTH, header_h), fill=theme["header"])
        draw.line((0, header_h, self.WIDTH, header_h), fill=theme["primary"], width=2)
        self._text(draw, (40, 24), "NIKKE", 38, theme["text"], bold=True)
        self._text(draw, (40, 75), "COMMANDER PROFILE / \u6307\u6325\u5b98\u6863\u6848", 22, theme["primary"])
        self._text_right(draw, (self.WIDTH - 40, 30), data.commander_name, 36, theme["text"], width=500, bold=True)

        # Sections
        y = header_h + 20
        for idx, (draw_fn, h) in enumerate(sections):
            fill = theme["panel"] if idx % 2 == 0 else theme["panel_alt"]
            draw_fn(draw, (40, y, self.WIDTH - 40, y + h), fill)
            y += h + panel_gap

        # Footer
        footer = f"{data.fetched_at}  \u00b7  v{data.plugin_version}  \u00b7  BlaBlaLink"
        self._text(draw, (40, y + 10), footer, 20, theme["muted"], width=800)

        path = self.output_dir / f"profile-{uuid.uuid4().hex}.png"
        canvas = canvas.convert("RGB") if canvas.mode != "RGB" else canvas
        canvas.save(path, "PNG", optimize=True)
        return str(path)

    def _collect_sections(self, data):
        sections = []
        if data.area_id or data.normal_campaign or data.hard_campaign:
            sections.append(self._basic_info_section(data))
        if data.synchro_level is not None or data.outpost_battle_level is not None:
            sections.append(self._outpost_section(data))
        if data.character_count > 0:
            sections.append(self._roster_stats_section(data))
        return sections

    def _basic_info_section(self, data):
        def draw_section(draw, box, fill):
            self._section_panel(draw, box, "BASIC INFO / \u57fa\u672c\u4fe1\u606f", fill=fill)
            x, y = box[0] + 30, box[1] + 55
            items = []
            if data.area_id:
                items.append(("\u533a\u670d ID", data.area_id))
            if data.normal_campaign:
                items.append(("\u666e\u901a\u4e3b\u7ebf", data.normal_campaign))
            if data.hard_campaign:
                items.append(("\u56f0\u96be\u4e3b\u7ebf", data.hard_campaign))
            for idx, (label, value) in enumerate(items):
                col_x = x + (idx % 3) * 370
                col_y = y + (idx // 3) * 70
                self._text(draw, (col_x, col_y), label, 18, PROFILE_THEME["muted"])
                self._text(draw, (col_x, col_y + 28), value, 28, PROFILE_THEME["text"], width=340, bold=True)

        item_count = sum(1 for v in [data.area_id, data.normal_campaign, data.hard_campaign] if v)
        rows = (item_count + 2) // 3
        height = 55 + rows * 70 + 20
        return draw_section, height

    def _outpost_section(self, data):
        def draw_section(draw, box, fill):
            self._section_panel(draw, box, "OUTPOST / \u524d\u54e8\u57fa\u5730", fill=fill)
            x, y = box[0] + 30, box[1] + 55
            items = []
            if data.synchro_level is not None:
                items.append(("\u540c\u6b65\u5668\u7b49\u7ea7", self._number(data.synchro_level)))
            if data.outpost_battle_level is not None:
                items.append(("\u524d\u54e8\u6218\u6597\u7b49\u7ea7", self._number(data.outpost_battle_level)))
            for idx, (label, value) in enumerate(items):
                col_x = x + idx * 550
                self._text(draw, (col_x, y), label, 18, PROFILE_THEME["muted"])
                self._text(draw, (col_x, y + 28), value, 42, PROFILE_THEME["secondary"], width=500, bold=True)

        item_count = sum(1 for v in [data.synchro_level, data.outpost_battle_level] if v is not None)
        height = 55 + 70 + 20
        return draw_section, height

    def _roster_stats_section(self, data):
        def draw_section(draw, box, fill):
            self._section_panel(draw, box, "ROSTER / \u59ae\u59ec\u7edf\u8ba1", fill=fill)
            x, y = box[0] + 30, box[1] + 55
            items = [
                ("\u89d2\u8272\u6570\u91cf", str(data.character_count)),
                ("\u6700\u9ad8\u7b49\u7ea7", f"Lv.{data.max_level}"),
                ("\u6700\u9ad8\u5355\u4f53\u6218\u529b", f"{data.max_combat:,}"),
            ]
            for idx, (label, value) in enumerate(items):
                col_x = x + idx * 370
                self._text(draw, (col_x, y), label, 18, PROFILE_THEME["muted"])
                self._text(draw, (col_x, y + 28), value, 36, PROFILE_THEME["primary"], width=340, bold=True)

        height = 55 + 70 + 20
        return draw_section, height
