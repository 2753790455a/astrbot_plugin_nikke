# SPDX-License-Identifier: GPL-3.0-or-later
"""Build ProfileDashboardData from raw API responses."""

from __future__ import annotations

from typing import Any

from .profile_models import ProfileDashboardData


class ProfileBuilder:
    def build(
        self,
        *,
        account: dict[str, Any],
        basic: dict[str, Any],
        outpost: dict[str, Any],
        roster: list[dict[str, Any]],
        fetched_at: str,
        plugin_version: str,
    ) -> ProfileDashboardData:
        commander_name = str(
            basic.get("nickname")
            or account.get("nickname")
            or account.get("role_name")
            or "指挥官"
        )
        area_id = str(account.get("area_id", ""))

        synchro_raw = outpost.get("synchro_level")
        synchro_level = int(synchro_raw) if synchro_raw not in (None, "", "0") else None

        outpost_raw = outpost.get("outpost_battle_level")
        outpost_battle_level = int(outpost_raw) if outpost_raw not in (None, "", "0") else None

        normal_campaign = str(
            basic.get("progress_normal_campaign")
            or basic.get("progress_campaign_normal")
            or ""
        ).strip() or None

        hard_campaign = str(
            basic.get("progress_hard_campaign")
            or basic.get("progress_campaign_hard")
            or ""
        ).strip() or None

        if roster:
            character_count = len(roster)
            max_level = max(int(c.get("lv", 0) or 0) for c in roster)
            max_combat = max(int(c.get("combat", 0) or 0) for c in roster)
        else:
            character_count = 0
            max_level = 0
            max_combat = 0

        return ProfileDashboardData(
            commander_name=commander_name,
            area_id=area_id,
            synchro_level=synchro_level,
            outpost_battle_level=outpost_battle_level,
            normal_campaign=normal_campaign,
            hard_campaign=hard_campaign,
            character_count=character_count,
            max_level=max_level,
            max_combat=max_combat,
            fetched_at=fetched_at,
            plugin_version=plugin_version,
        )
