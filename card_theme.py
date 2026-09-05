# SPDX-License-Identifier: GPL-3.0-or-later
"""角色主题只决定视觉，不参与账号数据计算。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharacterTheme:
    primary: str = "#91C8DC"
    secondary: str = "#D2E9F0"
    accent: str = "#59AFCB"
    background: str = "#11141B"
    panel: str = "#181E28"
    text: str = "#F4F6FA"
    muted: str = "#919BAB"


def character_theme(name_code: str, resource_id: str | None) -> CharacterTheme:
    if str(resource_id) == "191" or str(name_code) == "5004":
        return CharacterTheme(primary="#F28FB8", secondary="#FFD5E5", accent="#FF5F9B")
    if str(resource_id) == "470" or str(name_code) == "5101":
        return CharacterTheme(primary="#F18C7C", secondary="#FFD6BF", accent="#EE574B")
    return CharacterTheme()
