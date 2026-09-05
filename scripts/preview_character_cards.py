"""使用脱敏fixture生成可重复的UI2验收图片，不读取真实账号。"""

import argparse
import shutil
from dataclasses import replace
from pathlib import Path

from astrbot_plugin_nikke.asset_manager import AssetManager
from astrbot_plugin_nikke.character_card_renderer import CharacterCardRenderer
from astrbot_plugin_nikke.tests.test_card_builder import build_card


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output)
    manager = AssetManager(output / "cache", root / "assets", remote=args.remote)
    renderer = CharacterCardRenderer(output, root / "fonts", manager)
    original = build_card()
    cards = {
        "red-hood": original,
        "alice": replace(original, name_code="5004", resource_id="191", name_cn="爱丽丝", name_en="Alice",
                         corporation="TETRA", element="Fire", burst="Step3"),
        "fallback": replace(original, name_code="missing", resource_id=None, name_cn="未知角色 · 素材缺失预览", name_en="UNKNOWN NIKKE"),
    }
    for name, card in cards.items():
        generated = Path(renderer.render_character(card))
        path = output / f"{name}.png"
        shutil.move(str(generated), path)
        print(path)


if __name__ == "__main__":
    main()
