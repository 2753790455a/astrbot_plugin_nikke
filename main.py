# SPDX-License-Identifier: GPL-3.0-or-later
"""NIKKE 综合助手 AstrBot 插件。"""

from __future__ import annotations

import asyncio
import json
import os
import random
import secrets
import time
import zipfile
from datetime import datetime
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Context, Star, register

from .client import BlaBlaClient, BlaBlaError, CookieExpired
from .renderer import CardRenderer
from .storage import NikkeStore
from .web_service import BindingWebService


@register(
    "astrbot_plugin_nikke",
    "September",
    "NIKKE BlaBlaLink 账号练度、资料查询与每日汇总",
    "0.1.2",
    "https://github.com/September6969/astrbot_plugin_nikke",
)
class NikkePlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        self.plugin_dir = Path(__file__).resolve().parent
        self.data_dir = Path("data") / "nikke"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir = self.data_dir / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.extension_zip = self.data_dir / "nikke-bind-extension.zip"
        self.store = NikkeStore(self.data_dir)
        self.client = BlaBlaClient(
            int(self.config.get("request_timeout", 20)),
            lambda message: logger.info(f"[NIKKE诊断] {message}"),
        )
        self.renderer = CardRenderer(self.data_dir / "cards", self.plugin_dir / "fonts")
        self.web = BindingWebService(
            self.store,
            self.client,
            self.extension_zip,
            str(self.config.get("binding_api_key", "")),
        )
        self.public_base_url = str(
            self.config.get("public_base_url", "https://nikke.irises777.xyz")
        ).rstrip("/")
        self.web_host = str(self.config.get("web_host", "0.0.0.0"))
        self.web_port = int(self.config.get("web_port", 6210))
        self._directory: list[dict] = []
        self._background_tasks: list[asyncio.Task] = []
        self._closing = False
        self._pack_extension()
        self._background_tasks.append(asyncio.create_task(self._start_services()))

    def _pack_extension(self) -> None:
        extension_dir = self.plugin_dir / "extension"
        with zipfile.ZipFile(self.extension_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in extension_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(extension_dir))

    async def _start_services(self) -> None:
        try:
            await self.web.start(self.web_host, self.web_port)
            logger.info(f"[NIKKE] 绑定服务已监听 {self.web_host}:{self.web_port}")
        except Exception as exc:
            logger.error(f"[NIKKE] 绑定服务启动失败: {exc}")
        try:
            self._directory = await self.client.get_directory()
            logger.info(f"[NIKKE] 已载入 {len(self._directory)} 条妮姬目录")
        except Exception as exc:
            logger.warning(f"[NIKKE] 妮姬目录载入失败: {exc}")
        await self._scheduler_loop()

    async def _scheduler_loop(self) -> None:
        last_daily = ""
        last_summary = ""
        while not self._closing:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            daily_h = int(self.store.get_setting("daily_hour", self.config.get("daily_hour", 8)))
            daily_m = int(self.store.get_setting("daily_minute", self.config.get("daily_minute", 10)))
            summary_h = int(self.store.get_setting("summary_hour", self.config.get("summary_hour", 8)))
            summary_m = int(self.store.get_setting("summary_minute", self.config.get("summary_minute", 30)))
            if (now.hour, now.minute) == (daily_h, daily_m) and last_daily != today:
                last_daily = today
                asyncio.create_task(self._run_all_daily(today, stagger=True))
            if (now.hour, now.minute) == (summary_h, summary_m) and last_summary != today:
                last_summary = today
                asyncio.create_task(self._send_summary(today))
            await asyncio.sleep(20)

    @staticmethod
    def _qq_id(event: AstrMessageEvent) -> str:
        return str(event.get_sender_id())

    @staticmethod
    def _is_admin(event: AstrMessageEvent) -> bool:
        return bool(event.is_admin())

    def _account_or_error(self, event: AstrMessageEvent) -> dict:
        account = self.store.get_account(self._qq_id(event))
        if not account:
            raise ValueError("尚未绑定账号，请先发送 /nikke bind")
        return account

    def _name_map(self) -> dict[str, str]:
        return {
            str(item.get("name_code", "")): str(item.get("name_cn") or item.get("name_en") or "")
            for item in self._directory
        }

    def _find_directory(self, query: str) -> list[dict]:
        term = query.strip().casefold()
        return [
            item
            for item in self._directory
            if term in str(item.get("name_cn", "")).casefold()
            or term in str(item.get("name_en", "")).casefold()
            or term == str(item.get("name_code", "")).casefold()
        ]

    @staticmethod
    def _help_text(category: str = "") -> str:
        sections = {
            "账号": (
                "【账号绑定】\n"
                "/nikke bind — 私聊生成10分钟一次性绑定链接\n"
                "/nikke status — 查看绑定和Cookie状态\n"
                "/nikke me — 查看指挥官资料\n"
                "/nikke unbind — 删除自己的绑定与Cookie"
            ),
            "练度": (
                "【个人练度】\n"
                "/nikke roster — 生成妮姬练度总表\n"
                "/nikke progress — 查看同步器、前哨和战役进度\n"
                "/nikke character <名称> — 查看单个妮姬详情\n"
                "/nikke export — 导出个人练度JSON"
            ),
            "资料": (
                "【资料查询】\n"
                "/nikke info <名称> — 妮姬基础资料\n"
                "/nikke skill <名称> — 技能资料入口\n"
                "/nikke advise <名称> — 面谈资料入口\n"
                "/nikke stage <编号> — 关卡资料入口\n"
                "/nikke tower <类型> — 企业塔资料入口\n"
                "/nikke cube <名称> — 魔方资料入口\n"
                "/nikke collection <名称> — 收藏品资料入口\n"
                "/nikke image <名称> [类型] — 图片资料入口"
            ),
            "日常": (
                "【日常与推送】\n"
                "/nikke daily — 检查自己的登录和每日状态\n"
                "/nikke push on|off — 加入或退出群汇总\n"
                "/nikke claim — 奖励领取（当前安全禁用）\n"
                "/nikke cdk <兑换码> — 显示官方手动兑换入口"
            ),
            "管理": (
                "【管理员】\n"
                "/nikke group set — 将当前群设为汇总目标\n"
                "/nikke schedule HH:MM — 设置每日检查时间\n"
                "/nikke summary HH:MM — 设置汇总发送时间\n"
                "/nikke run — 立即执行汇总\n"
                "/nikke health — 查看插件健康状态"
            ),
        }
        aliases = {
            "account": "账号", "bind": "账号",
            "roster": "练度", "progress": "练度",
            "info": "资料", "data": "资料",
            "daily": "日常", "push": "日常",
            "admin": "管理",
        }
        selected = aliases.get(category.strip().lower(), category.strip())
        if selected in sections:
            return sections[selected] + "\n\n发送 /nikke help 查看全部指令。"
        return (
            "NIKKE 综合助手 0.1.2\n\n"
            + "\n\n".join(sections.values())
            + "\n\n帮助分类：/nikke help 账号|练度|资料|日常|管理\n"
            "安全提示：不要在群里发送Cookie、密码或绑定链接。"
        )

    @filter.command("nikke help")
    async def nikke_help(self, event: AstrMessageEvent, category: str = ""):
        """查看全部或分类的NIKKE综合助手指令。"""
        yield event.plain_result(self._help_text(category))

    @filter.command("nikke bind")
    async def bind(self, event: AstrMessageEvent):
        """生成十分钟有效的安全绑定链接。"""
        if not event.is_private_chat() and not bool(self.config.get("allow_group_bind", False)):
            yield event.plain_result("为防止绑定链接被他人抢先使用，请私聊机器人发送 /nikke bind。")
            return
        token = secrets.token_urlsafe(36)
        self.store.create_bind_session(token, self._qq_id(event), 600)
        url = f"{self.public_base_url}/bind/{token}"
        yield event.plain_result(f"安全绑定链接（10分钟、仅可使用一次）：\n{url}\n请勿转发。账号密码只在BlaBlaLink官网输入。")

    @filter.command("nikke unbind")
    async def unbind(self, event: AstrMessageEvent):
        """解除自己的BlaBlaLink账号。"""
        removed = self.store.delete_account(self._qq_id(event))
        yield event.plain_result("已解除绑定。" if removed else "当前QQ尚未绑定。")

    @filter.command("nikke status")
    async def status(self, event: AstrMessageEvent):
        """检查绑定和Cookie状态。"""
        account = self.store.get_account(self._qq_id(event), with_cookie=False)
        if not account:
            yield event.plain_result("未绑定，请发送 /nikke bind")
            return
        state = "有效" if account["cookie_valid"] else "已失效，请重新绑定"
        yield event.plain_result(
            f"已绑定：{account['nickname'] or account['role_name'] or '未命名指挥官'}\n"
            f"区服ID：{account['area_id'] or '待识别'}\nCookie：{state}\n"
            f"每日汇总：{'开启' if account['push_enabled'] else '关闭'}"
        )

    @filter.command("nikke me")
    async def me(self, event: AstrMessageEvent):
        """生成个人账号概览卡。"""
        try:
            account = self._account_or_error(event)
            data = await self.client.get_profile(account)
            basic, outpost = data["basic"], data["outpost"]
            rows = [
                ("指挥官", str(basic.get("nickname") or account.get("nickname") or account.get("role_name") or "未知")),
                ("区服", str(account.get("area_id") or "未知")),
                ("同步器", str(outpost.get("synchro_level", 0))),
                ("前哨等级", str(outpost.get("outpost_battle_level", 0))),
                ("普通主线", str(basic.get("progress_normal_campaign", basic.get("progress_campaign_normal", "未知")))),
                ("困难主线", str(basic.get("progress_hard_campaign", basic.get("progress_campaign_hard", "未知")))),
            ]
            path = self.renderer.render("指挥官档案", "BlaBlaLink 私人数据", rows)
            yield event.image_result(path)
        except CookieExpired:
            self.store.mark_cookie_invalid(self._qq_id(event))
            yield event.plain_result("登录状态已失效，请重新发送 /nikke bind")
        except (BlaBlaError, ValueError, RuntimeError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("nikke roster")
    async def roster(self, event: AstrMessageEvent):
        """生成自己的妮姬练度表。"""
        try:
            account = self._account_or_error(event)
            characters = await self.client.get_roster(account, True)
            path = self.renderer.render_roster(
                account.get("nickname") or account.get("role_name") or "指挥官",
                characters,
                self._name_map(),
            )
            yield event.image_result(path)
        except CookieExpired:
            self.store.mark_cookie_invalid(self._qq_id(event))
            yield event.plain_result("登录状态已失效，请重新绑定。")
        except Exception as exc:
            logger.warning(f"[NIKKE] roster 查询失败: {type(exc).__name__}: {exc}")
            yield event.plain_result(f"练度查询失败：{exc}")

    @filter.command("nikke progress")
    async def progress(self, event: AstrMessageEvent):
        """查看同步器、前哨和主线进度。"""
        async for result in self.me(event):
            yield result

    @filter.command("nikke character")
    async def character(self, event: AstrMessageEvent, name: str):
        """查询自己指定妮姬的练度。"""
        try:
            account = self._account_or_error(event)
            matches = self._find_directory(name)
            if not matches:
                raise ValueError("没有找到该妮姬")
            target = matches[0]
            roster = await self.client.get_roster(account, True)
            code = str(target.get("name_code", ""))
            item = next((x for x in roster if str(x.get("name_code", "")) == code), None)
            if not item:
                raise ValueError("该账号未持有这名妮姬")
            rows = [
                ("等级 / 战力", f"Lv.{item.get('lv', 1)} / {item.get('combat', 0)}"),
                ("技能", f"{item.get('skill1_lv', 1)} / {item.get('skill2_lv', 1)} / {item.get('ulti_skill_lv', 1)}"),
                ("突破 / 核心", f"{item.get('grade', 0)} / {item.get('core', 0)}"),
                ("好感度", str(item.get("attractive_lv", "未知"))),
                ("收藏品", f"{item.get('favorite_item_tid', 0)}  Lv.{item.get('favorite_item_lv', 0)}"),
                ("魔方", f"{item.get('harmony_cube_tid', 0)}  Lv.{item.get('harmony_cube_lv', 0)}"),
                ("AEL", str(self.client.calculate_ael(item))),
            ]
            path = self.renderer.render(target.get("name_cn") or target.get("name_en") or name, "个人练度详情", rows)
            yield event.image_result(path)
        except Exception as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("nikke export")
    async def export(self, event: AstrMessageEvent):
        """导出个人练度JSON。"""
        try:
            account = self._account_or_error(event)
            characters = await self.client.get_roster(account, True)
            safe_id = self._qq_id(event)
            path = self.export_dir / f"nikke-{safe_id}-{int(time.time())}.json"
            path.write_text(json.dumps(characters, ensure_ascii=False, indent=2), encoding="utf-8")
            yield event.plain_result(f"JSON已生成：{path.name}\n当前适配器不支持直接发送文件时，请联系管理员从服务器下载。")
        except Exception as exc:
            yield event.plain_result(f"导出失败：{exc}")

    @filter.command("nikke info")
    async def info(self, event: AstrMessageEvent, name: str):
        """查询妮姬基础资料。"""
        matches = self._find_directory(name)
        if not matches:
            yield event.plain_result("没有找到该妮姬。")
            return
        item = matches[0]
        rows = [
            ("中文 / 英文", f"{item.get('name_cn','')} / {item.get('name_en','')}"),
            ("稀有度", str(item.get("rare") or "未知")),
            ("属性", str(item.get("element") or "未知")),
            ("武器", str(item.get("weapon") or "未知")),
            ("爆裂阶段", str(item.get("burst") or "未知")),
            ("企业", str(item.get("corporation") or "未知")),
        ]
        path = self.renderer.render(item.get("name_cn") or item.get("name_en") or name, "妮姬基础资料", rows)
        yield event.image_result(path)

    @filter.command("nikke skill")
    async def skill(self, event: AstrMessageEvent, name: str):
        """提供妮姬技能资料入口。"""
        matches = self._find_directory(name)
        if not matches:
            yield event.plain_result("没有找到该妮姬。")
            return
        item = matches[0]
        rows = [
            ("角色", str(item.get("name_cn") or item.get("name_en"))),
            ("状态", "首版仅展示官方目录字段；技能全文数据源许可核对后启用"),
            ("BlaBlaLink", "https://www.blablalink.com/shiftyspad/nikke-list/all"),
        ]
        yield event.image_result(self.renderer.render("技能资料", "开放数据优先", rows))

    async def _reference_card(self, event: AstrMessageEvent, kind: str, query: str):
        rows = [
            ("查询", query),
            ("状态", "数据源许可核对中，当前不复制第三方攻略正文"),
            ("官方社区", "https://www.blablalink.com/"),
        ]
        yield event.image_result(self.renderer.render(kind, "资料导航", rows))

    @filter.command("nikke advise")
    async def advise(self, event: AstrMessageEvent, name: str):
        """查询面谈资料入口。"""
        async for result in self._reference_card(event, "面谈资料", name): yield result

    @filter.command("nikke stage")
    async def stage(self, event: AstrMessageEvent, stage_id: str):
        """查询关卡资料入口。"""
        async for result in self._reference_card(event, "关卡资料", stage_id): yield result

    @filter.command("nikke tower")
    async def tower(self, event: AstrMessageEvent, tower_type: str):
        """查询企业塔资料入口。"""
        async for result in self._reference_card(event, "企业塔资料", tower_type): yield result

    @filter.command("nikke cube")
    async def cube(self, event: AstrMessageEvent, name: str):
        """查询魔方资料入口。"""
        async for result in self._reference_card(event, "魔方资料", name): yield result

    @filter.command("nikke collection")
    async def collection(self, event: AstrMessageEvent, name: str):
        """查询收藏品资料入口。"""
        async for result in self._reference_card(event, "收藏品资料", name): yield result

    @filter.command("nikke image")
    async def image(self, event: AstrMessageEvent, name: str, image_type: str = "头像"):
        """查询妮姬图片入口。"""
        async for result in self._reference_card(event, f"妮姬图片 · {image_type}", name): yield result

    async def _run_daily_for_account(self, account: dict, day: str) -> tuple[str, str]:
        qq_id = str(account["qq_id"])
        run_key = f"{day}:{qq_id}:daily"
        if not self.store.claim_run(run_key, qq_id, "daily"):
            return account.get("nickname") or qq_id, "今日已执行"
        try:
            await self.client.get_profile(account)
            if bool(self.config.get("enable_daily_actions", False)):
                signin_key = f"{day}:{qq_id}:signin"
                status = await self.client.get_daily_signin(account)
                if not status["found"]:
                    detail = "登录有效；未找到签到任务"
                elif status["completed"]:
                    detail = "登录有效；今日已经签到"
                elif self.store.claim_run(signin_key, qq_id, "signin"):
                    try:
                        detail = "登录有效；" + await self.client.perform_daily_signin(account)
                        self.store.finish_run(signin_key, "success", detail)
                    except Exception as exc:
                        self.store.finish_run(signin_key, "failed", type(exc).__name__)
                        raise
                else:
                    detail = "登录有效；签到已执行或正在执行"
            else:
                try:
                    status = await self.client.get_daily_signin(account)
                    signin = "已签到" if status["completed"] else "待签到" if status["found"] else "未找到签到任务"
                    detail = f"登录有效；自动签到未启用；当前{signin}"
                except BlaBlaError as exc:
                    detail = f"登录有效；自动签到未启用；{exc}"
            self.store.finish_run(run_key, "success", detail)
            return account.get("nickname") or qq_id, detail
        except CookieExpired:
            self.store.mark_cookie_invalid(qq_id)
            self.store.finish_run(run_key, "expired", "Cookie失效")
            return account.get("nickname") or qq_id, "Cookie失效，请重新绑定"
        except Exception as exc:
            detail = f"失败：{type(exc).__name__}"
            self.store.finish_run(run_key, "failed", detail)
            return account.get("nickname") or qq_id, detail

    async def _run_all_daily(self, day: str, stagger: bool = False) -> list[tuple[str, str]]:
        accounts = self.store.list_accounts(push_only=True, with_cookie=True)
        semaphore = asyncio.Semaphore(max(1, int(self.config.get("max_concurrency", 2))))

        async def run(account):
            if stagger:
                await asyncio.sleep(random.uniform(0, 15 * 60))
            async with semaphore:
                return await self._run_daily_for_account(account, day)

        results = await asyncio.gather(*(run(account) for account in accounts))
        self.store.set_setting(f"daily_results:{day}", results)
        return results

    async def _send_summary(self, day: str) -> None:
        group_umo = self.store.get_setting("summary_group_umo", "")
        if not group_umo:
            logger.warning("[NIKKE] 尚未配置每日汇总群")
            return
        results = self.store.get_setting(f"daily_results:{day}", [])
        if not results:
            results = await self._run_all_daily(day)
        path = self.renderer.render_summary([(str(a), str(b)) for a, b in results])
        await self.context.send_message(group_umo, MessageChain([Image.fromFileSystem(path)]))

    @filter.command("nikke daily")
    async def daily(self, event: AstrMessageEvent):
        """手动检查自己的每日任务状态。"""
        try:
            account = self._account_or_error(event)
            name, detail = await self._run_daily_for_account(account, datetime.now().strftime("%Y-%m-%d"))
            yield event.plain_result(f"{name}：{detail}")
        except Exception as exc:
            yield event.plain_result(f"执行失败：{exc}")

    @filter.command("nikke claim")
    async def claim(self, event: AstrMessageEvent):
        """领取已满足条件的社区奖励。"""
        if not bool(self.config.get("enable_daily_actions", False)):
            yield event.plain_result("签到写操作当前由管理员关闭；可使用 /nikke daily 查看只读状态。")
            return
        try:
            account = self._account_or_error(event)
            day = datetime.now().strftime("%Y-%m-%d")
            run_key = f"{day}:{self._qq_id(event)}:signin"
            status = await self.client.get_daily_signin(account)
            if status["completed"]:
                yield event.plain_result("今日已经签到，无需重复执行。")
                return
            if not self.store.claim_run(run_key, self._qq_id(event), "signin"):
                yield event.plain_result("今日签到已经执行或正在执行，不会重复提交。")
                return
            try:
                result = await self.client.perform_daily_signin(account)
                self.store.finish_run(run_key, "success", result)
                yield event.plain_result(result)
            except Exception as exc:
                self.store.finish_run(run_key, "failed", type(exc).__name__)
                raise
        except Exception as exc:
            yield event.plain_result(f"签到失败：{exc}")

    @filter.command("nikke cdk")
    async def cdk(self, event: AstrMessageEvent, code: str):
        """打开官方CDK兑换入口。"""
        masked = code[:2] + "***" + code[-2:] if len(code) > 4 else "***"
        yield event.plain_result(f"兑换码 {masked} 请在官方入口手动提交：https://www.blablalink.com/cdk\n当前版本不会记录或代提交CDK。")

    @filter.command("nikke push")
    async def push(self, event: AstrMessageEvent, state: str):
        """开启或关闭每日群汇总。"""
        enabled = state.lower() in {"on", "开", "开启", "1"}
        if state.lower() not in {"on", "off", "开", "关", "开启", "关闭", "1", "0"}:
            yield event.plain_result("用法：/nikke push on 或 /nikke push off")
            return
        changed = self.store.set_push(self._qq_id(event), enabled)
        yield event.plain_result(("每日汇总已开启。" if enabled else "每日汇总已关闭。") if changed else "请先绑定账号。")

    @filter.command("nikke group set")
    async def group_set(self, event: AstrMessageEvent):
        """管理员将当前会话设为每日汇总目标。"""
        if not self._is_admin(event):
            yield event.plain_result("仅管理员可配置汇总群。")
            return
        self.store.set_setting("summary_group_umo", event.unified_msg_origin)
        yield event.plain_result(f"每日汇总目标已设为当前会话：{event.unified_msg_origin}")

    @staticmethod
    def _parse_clock(value: str) -> tuple[int, int]:
        hour, minute = value.split(":", 1)
        h, m = int(hour), int(minute)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("时间范围错误")
        return h, m

    @filter.command("nikke schedule")
    async def schedule(self, event: AstrMessageEvent, clock: str):
        """管理员设置每日任务开始时间。"""
        if not self._is_admin(event):
            yield event.plain_result("仅管理员可修改时间。")
            return
        try:
            h, m = self._parse_clock(clock)
            self.store.set_setting("daily_hour", h)
            self.store.set_setting("daily_minute", m)
            yield event.plain_result(f"每日任务时间已设为 {h:02d}:{m:02d}。")
        except Exception:
            yield event.plain_result("用法：/nikke schedule HH:MM")

    @filter.command("nikke summary")
    async def summary(self, event: AstrMessageEvent, clock: str):
        """管理员设置每日汇总时间。"""
        if not self._is_admin(event):
            yield event.plain_result("仅管理员可修改时间。")
            return
        try:
            h, m = self._parse_clock(clock)
            self.store.set_setting("summary_hour", h)
            self.store.set_setting("summary_minute", m)
            yield event.plain_result(f"每日汇总时间已设为 {h:02d}:{m:02d}。")
        except Exception:
            yield event.plain_result("用法：/nikke summary HH:MM")

    @filter.command("nikke run")
    async def run(self, event: AstrMessageEvent):
        """管理员立即执行并发送汇总。"""
        if not self._is_admin(event):
            yield event.plain_result("仅管理员可执行全量任务。")
            return
        day = datetime.now().strftime("%Y-%m-%d")
        results = await self._run_all_daily(day)
        path = self.renderer.render_summary(results)
        yield event.image_result(path)

    @filter.command("nikke health")
    async def health(self, event: AstrMessageEvent):
        """管理员查看插件健康状态。"""
        if not self._is_admin(event):
            yield event.plain_result("仅管理员可查看。")
            return
        accounts = self.store.list_accounts(with_cookie=False)
        yield event.plain_result(
            f"NIKKE插件 0.1.2\n账号：{len(accounts)}\n目录：{len(self._directory)}\n"
            f"绑定服务：{self.web_host}:{self.web_port}\n自动写操作：{'启用' if self.config.get('enable_daily_actions', False) else '关闭'}"
        )

    async def terminate(self):
        self._closing = True
        await self.web.stop()
        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        logger.info("[NIKKE] 插件已停止")
