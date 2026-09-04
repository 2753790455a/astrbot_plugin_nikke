# NIKKE 综合助手

面向 AstrBot + NapCat/OneBot 的 BlaBlaLink 账号练度与资料查询插件。

## 当前功能

- Chrome/Edge MV3 扩展辅助绑定，密码只提交给 BlaBlaLink 官网。
- Cookie 加密存储、十分钟单次绑定令牌、账号隔离。
- 指挥官资料、同步器、前哨与主线进度。
- 妮姬目录、个人角色列表、技能等级、突破、核心、收藏品、魔方和 AEL。
- NIKKE 风格图片卡、JSON 导出、每日账号健康检查与群汇总。
- 面谈、关卡、企业塔、魔方、收藏品及图片命令已经提供稳定入口；只有在数据许可明确后才会加入第三方正文。

## 安全边界

- 插件和扩展不保存账号密码。
- 扩展仅能访问 `*.blablalink.com` 与 `nikke.irises777.xyz`。
- 自动点赞、关注、浏览、资料修改和自动 CDK 均未实现。
- 社区签到和领奖属于写操作，默认关闭；在真实账号契约测试完成前只检查登录状态。

## 部署

1. 将目录放入 `AstrBot/data/plugins/astrbot_plugin_nikke`。
2. 将 AstrBot 数据卷中的 `data/nikke` 持久化并备份。
3. 让 Caddy 将 `nikke.irises777.xyz` 反代到 AstrBot 容器的 `6210` 端口。
4. DNS 添加 `nikke.irises777.xyz A 8.148.14.155`。
5. 在 QQ 中发送 `/nikke help`。

## 许可证与来源

本项目采用 GPL-3.0-or-later。部分 API 适配和算法基于
[ExiaProject/ExiaInvasion](https://github.com/ExiaProject/ExiaInvasion) 移植，详见 `NOTICE`。

