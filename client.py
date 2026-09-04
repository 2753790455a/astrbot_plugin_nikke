# SPDX-License-Identifier: GPL-3.0-or-later
"""BlaBlaLink API 适配层。

接口与恢复策略基于 ExiaProject/ExiaInvasion GPL-3.0 源码移植。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

import httpx


API_BASE = "https://api.blablalink.com"
PLAYER_INFO = "/api/ugc/direct/standalonesite/User/GetUserGamePlayerInfo"
CHECK_LOGIN = "/api/user/CheckLogin"
USER_INFO_NEW = "/api/ugc/proxy/standalonesite/User/GetUserInfoNew"
PRIVACY_SETTING = "/api/ugc/direct/standalonesite/User/GetUserPrivacySetting"
PROFILE = "/api/game/proxy/Game/GetUserProfileBasicInfo"
OUTPOST = "/api/game/proxy/Game/GetUserProfileOutpostInfo"
CHARACTERS = "/api/game/proxy/Game/GetUserCharacters"
CHARACTER_DETAILS = "/api/game/proxy/Game/GetUserCharacterDetails"

NIKKE_DIRECTORY_ZH = "https://sg-tools-cdn.blablalink.com/jz-26/ww-14/c4619ec83335bcfd7b23e43600520dc7.json"
NIKKE_DIRECTORY_EN = "https://sg-tools-cdn.blablalink.com/yl-57/hd-03/1bf030193826e243c2e195f951a4be00.json"


class BlaBlaError(RuntimeError):
    def __init__(self, message: str, code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = str(code)
        self.endpoint = endpoint


class CookieExpired(BlaBlaError):
    pass


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    game_uid: str
    game_openid: str
    role_name: str = ""
    nickname: str = ""
    area_id: str = ""


class BlaBlaClient:
    def __init__(self, timeout: int = 20, diagnostic: Callable[[str], None] | None = None):
        self.timeout = httpx.Timeout(timeout, connect=min(timeout, 10))
        self.diagnostic = diagnostic

    def _diagnose(self, message: str) -> None:
        if not self.diagnostic:
            return
        try:
            self.diagnostic(message)
        except Exception:
            pass

    @staticmethod
    def parse_cookie(cookie: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for part in cookie.split(";"):
            if "=" not in part:
                continue
            name, value = part.strip().split("=", 1)
            values[name] = value
        return values

    async def _post(self, path: str, cookie: str, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = path.rsplit("/", 1)[-1]
        self._diagnose(f"{endpoint} 请求开始；payload_keys={sorted(payload)}")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cookie": cookie,
            "Origin": "https://www.blablalink.com",
            "Referer": "https://www.blablalink.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.post(API_BASE + path, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            self._diagnose(f"{endpoint} HTTP失败；status={exc.response.status_code}")
            raise BlaBlaError(f"{endpoint} HTTP {exc.response.status_code}", str(exc.response.status_code), endpoint) from exc
        except (httpx.HTTPError, ValueError) as exc:
            self._diagnose(f"{endpoint} 请求异常；type={type(exc).__name__}")
            raise BlaBlaError(f"{endpoint} 请求失败：{type(exc).__name__}", endpoint=endpoint) from exc
        code = str(data.get("code", data.get("retcode", data.get("ret_code", ""))))
        response_data = data.get("data")
        data_keys = sorted(response_data)[:20] if isinstance(response_data, dict) else []
        self._diagnose(f"{endpoint} 响应；code={code or 'missing'}；data_keys={data_keys}")
        if code not in ("", "0"):
            message = str(data.get("message", data.get("msg", f"接口返回 {code}")))
            if code in {"1000002", "1000003", "1001001", "401", "403"}:
                raise CookieExpired("登录状态已失效，请重新绑定", code, endpoint)
            raise BlaBlaError(message, code, endpoint)
        return data

    async def validate_cookie(self, cookie: str) -> ValidationResult:
        values = self.parse_cookie(cookie)
        game_uid = values.get("game_uid", "")
        game_openid = values.get("game_openid", "")
        missing = [name for name in ("game_token", "game_uid", "game_openid") if not values.get(name)]
        self._diagnose(f"Cookie快照；count={len(values)}；names={sorted(values)}")
        if missing:
            raise BlaBlaError("缺少必要 Cookie：" + ", ".join(missing))

        player: dict[str, Any] | None = None
        player_error: BlaBlaError | None = None
        for delay in (0, 1, 2):
            if delay:
                await asyncio.sleep(delay)
            try:
                player = await self._post(PLAYER_INFO, cookie, {})
                break
            except BlaBlaError as exc:
                player_error = exc
                if exc.code != "1300015" or delay == 2:
                    if exc.code == "1300015":
                        break
                    break

        # BlaBlaLink 有时无法通过空请求推断玩家；按 Exia 的恢复链路显式传入标识。
        if player is None or not player.get("data", {}).get("area_id"):
            try:
                player = await self._post(
                    PLAYER_INFO,
                    cookie,
                    {"intl_openid": game_openid},
                )
                player_error = None
            except BlaBlaError as exc:
                player_error = exc

        # 某些账号的 game_openid 只是网页登录标识，需要先换取正式 intl_openid。
        if player is None or not player.get("data", {}).get("area_id"):
            canonical_openid = ""
            try:
                user_info = await self._post(USER_INFO_NEW, cookie, {})
                user_data = user_info.get("data", {}) or {}
                canonical_openid = str(
                    (user_data.get("info", {}) or {}).get("intl_openid")
                    or user_data.get("intl_openid")
                    or ""
                ).strip()
            except BlaBlaError:
                canonical_openid = ""
            if canonical_openid:
                try:
                    # 隐私查询会促使官网链路完成账号上下文初始化；失败不阻断后续识别。
                    await self._post(PRIVACY_SETTING, cookie, {"intl_openid": canonical_openid})
                except BlaBlaError:
                    pass
                try:
                    player = await self._post(
                        PLAYER_INFO,
                        cookie,
                        {"intl_openid": canonical_openid},
                    )
                    game_openid = canonical_openid
                    player_error = None
                except BlaBlaError as exc:
                    player_error = exc

        if player is None or not player.get("data", {}).get("area_id"):
            try:
                await self._post(CHECK_LOGIN, cookie, {})
            except BlaBlaError:
                if player_error:
                    raise player_error
                raise
            return ValidationResult(True, game_uid, game_openid)

        info = player.get("data", {})
        area_id = str(info.get("area_id", ""))
        role_name = str(info.get("role_name", ""))
        nickname = role_name
        try:
            basic = await self._post(
                PROFILE,
                cookie,
                {"nikke_area_id": int(area_id), "intl_open_id": game_openid},
            )
            nickname = str(basic.get("data", {}).get("basic_info", {}).get("nickname", "")) or role_name
        except BlaBlaError:
            pass
        return ValidationResult(True, game_uid, game_openid, role_name, nickname, area_id)

    async def get_profile(self, account: dict[str, Any]) -> dict[str, Any]:
        area_id = str(account.get("area_id", ""))
        if not area_id:
            validated = await self.validate_cookie(account["cookie"])
            area_id = validated.area_id
        payload = {"nikke_area_id": int(area_id)}
        if account.get("game_openid"):
            payload["intl_open_id"] = account["game_openid"]
        basic, outpost = await asyncio.gather(
            self._post(PROFILE, account["cookie"], payload),
            self._post(OUTPOST, account["cookie"], {"nikke_area_id": int(area_id)}),
        )
        return {
            "basic": basic.get("data", {}).get("basic_info", {}),
            "outpost": outpost.get("data", {}).get("outpost_info", {}),
        }

    async def get_roster(self, account: dict[str, Any], include_details: bool = True) -> list[dict[str, Any]]:
        area_id = int(account["area_id"])
        openid = account.get("game_openid", "")
        roster_resp = await self._post(
            CHARACTERS,
            account["cookie"],
            {"intl_open_id": openid, "nikke_area_id": area_id},
        )
        data = roster_resp.get("data", {})
        roster = data.get("characters", data.get("user_characters", [])) or []
        if not include_details or not roster:
            return roster
        codes = list(dict.fromkeys(str(c.get("name_code", "")) for c in roster if c.get("name_code")))
        detail_resp = await self._post(
            CHARACTER_DETAILS,
            account["cookie"],
            {"intl_open_id": openid, "nikke_area_id": area_id, "name_codes": codes},
        )
        details_data = detail_resp.get("data", {})
        details = details_data.get("character_details", []) or []
        effects = details_data.get("state_effects", []) or []
        effects_map = {str(effect.get("id")): effect for effect in effects}
        by_code: dict[str, dict[str, Any]] = {}
        slots = ("head", "torso", "arm", "leg")
        for detail in details:
            equipment_effects = []
            for slot in slots:
                for index in range(1, 4):
                    effect_id = detail.get(f"{slot}_equip_option{index}_id")
                    effect = effects_map.get(str(effect_id))
                    for function in (effect or {}).get("function_details", []) or []:
                        equipment_effects.append(
                            {
                                "function_type": function.get("function_type", ""),
                                "function_value": abs(float(function.get("function_value", 0) or 0)),
                                "level": function.get("level"),
                            }
                        )
            by_code[str(detail.get("name_code"))] = {
                **detail,
                "equipment_effects": equipment_effects,
            }
        merged = []
        for item in roster:
            code = str(item.get("name_code", ""))
            merged.append({**item, **by_code.get(code, {})})
        return merged

    async def get_directory(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            zh_resp, en_resp = await asyncio.gather(
                client.get(NIKKE_DIRECTORY_ZH), client.get(NIKKE_DIRECTORY_EN)
            )
        zh_resp.raise_for_status()
        en_resp.raise_for_status()
        zh_data = zh_resp.json()
        en_data = en_resp.json()
        en_map = {str(x.get("id")): x for x in en_data if isinstance(x, dict)}
        result = []
        for zh in zh_data:
            en = en_map.get(str(zh.get("id")), {})
            result.append(
                {
                    "id": zh.get("id"),
                    "resource_id": zh.get("resource_id"),
                    "name_code": zh.get("name_code"),
                    "name_cn": (zh.get("name_localkey") or {}).get("name", ""),
                    "name_en": (en.get("name_localkey") or {}).get("name", ""),
                    "element": ((zh.get("element_id") or {}).get("element") or {}).get("element", ""),
                    "weapon": ((zh.get("shot_id") or {}).get("element") or {}).get("weapon_type", ""),
                    "burst": zh.get("use_burst_skill"),
                    "corporation": zh.get("corporation"),
                    "rare": zh.get("original_rare"),
                }
            )
        return result

    @staticmethod
    def calculate_ael(character: dict[str, Any]) -> float:
        atk = elem = 0.0
        effects = character.get("equipment_effects", character.get("effects", [])) or []
        for effect in effects:
            kind = str(effect.get("function_type", "")).lower()
            value = abs(float(effect.get("function_value", 0))) / 10000
            if "attack" in kind or kind in {"atk", "statatk", "1"}:
                atk += value
            if "element" in kind or kind in {"elem", "incelementdmg", "2"}:
                elem += value
        grade = int(character.get("grade", 0) or 0)
        core = int(character.get("core", 0) or 0)
        return round((1 + 0.9 * atk) * (1 + elem + 0.10) * (1 + 0.03 * grade + 0.02 * core), 4)
