# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile dashboard data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProfileDashboardData:
    commander_name: str
    area_id: str
    synchro_level: int | None
    outpost_battle_level: int | None
    normal_campaign: str | None
    hard_campaign: str | None
    character_count: int
    max_level: int
    max_combat: int
    fetched_at: str
    plugin_version: str
