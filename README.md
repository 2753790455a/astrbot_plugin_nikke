# NIKKE 综合助手

面向 AstrBot + NapCat/OneBot 的 BlaBlaLink 账号练度查询插件。当前版本是早期测试版，建议由具备 Docker 和反向代理经验的机器人维护者部署。

## 功能状态

已实现：

- Chrome/Edge MV3 扩展辅助绑定，密码和验证码只提交给 BlaBlaLink 官网。
- Cookie 加密存储、十分钟单次绑定令牌和每个 QQ 独立会话。
- 指挥官资料、同步器、前哨、主线进度及个人妮姬列表查询。
- 技能等级、突破、核心、装备词条和 AEL 数据整理。
- NIKKE 风格图片卡、JSON 导出、每日账号健康检查与群汇总框架。

尚未完成或默认禁用：

- 社区签到和奖励领取尚未通过真实写接口验收，代码不会执行写操作。
- 面谈、关卡、企业塔、魔方、收藏品和图片命令目前是资料导航入口。
- Prydwen、NIKKE.gg 等未明确授权的攻略正文不会复制到本项目。

## 安全边界

- 插件和扩展不保存账号密码。
- 扩展仅能访问 `*.blablalink.com` 与配置的绑定域名。
- 服务端只接受 BlaBlaLink 域 Cookie，并限制名称、数量、单项和总长度。
- 诊断日志只记录 Cookie 名称、接口名、业务码和响应字段，不记录 Cookie 值。
- 默认只能在私聊中生成绑定链接，避免群成员抢先使用链接提交账号。
- 自动点赞、关注、浏览、资料修改和自动 CDK 均未实现。
- 社区签到和领奖属于写操作，默认关闭；在真实账号契约测试完成前只检查登录状态。

## 最小部署

要求：AstrBot `>=4.24,<5`、Python 3.10+、可访问 BlaBlaLink 的网络，以及 HTTPS 域名。

1. 将目录放入 `AstrBot/data/plugins/astrbot_plugin_nikke`。
2. 安装 `requirements.txt` 中的依赖并重启 AstrBot。
3. 持久化 AstrBot 的 `data/nikke` 目录；其中包含数据库和 `secret.key`，两者必须一起备份。
4. 将插件配置 `public_base_url` 改为自己的 HTTPS 域名。
5. 使用 Caddy/Nginx 将公网 HTTPS 反代到 AstrBot 容器网络中的 `6210` 端口。
6. **不要**把 `6210`、AstrBot 后台或 NapCat 后台直接映射到公网。
7. 在 QQ 中发送 `/nikke help`，再发送 `/nikke bind` 完成绑定。

仓库中的 `deploy/Caddyfile` 和 `deploy/docker-compose.caddy.yml` 是示例。Caddy 与 AstrBot 必须加入同一个 Docker 网络；这种布局下插件在容器内监听 `0.0.0.0:6210`，但宿主机不发布该端口。

最小 Caddy 配置：

```caddyfile
nikke.example.com {
    reverse_proxy astrbot:6210
}
```

## 常用命令

- `/nikke bind`：生成十分钟有效的一次性链接。
- `/nikke status`、`/nikke me`：查看绑定和指挥官资料。
- `/nikke roster`、`/nikke character <名称>`：查看个人练度。
- `/nikke export`：生成 JSON；当前适配器不支持文件直发时会返回服务器文件名。
- `/nikke push on|off`：控制是否参与每日汇总。
- `/nikke health`：管理员查看插件状态。

如确实需要在可信群中生成链接，可将 `allow_group_bind` 设为 `true`；不建议对公开群开启。

## 常见故障

### `MetaData no user account`

先确认官网个人页可以看到 NIKKE 等级和战役数据，再重新安装最新版绑定扩展并创建新链接。0.1.1 起扩展只读取浏览器实际会发送给 `www.blablalink.com` 的 Cookie，服务端也会执行 `game_openid` 和正式 `intl_openid` 后备识别。

管理员可检查 AstrBot 日志中的 `[NIKKE诊断]` 行。日志只包含接口名、业务码、响应字段和 Cookie 名称；不要要求用户发送 Cookie 值或 Cookie-Editor 导出文件。

### HTTPS 或扩展请求失败

- 确认 DNS 指向服务器，云安全组开放 TCP 80/443。
- 确认 Caddy 与 AstrBot 位于同一 Docker 网络。
- 访问 `https://你的域名/healthz`，应返回 `ok: true`。
- 扩展跨域请求只允许来自 Chrome/Edge 扩展页，不再使用 `Access-Control-Allow-Origin: *`。

### 容器迁移后无法解密

必须同时迁移 `data/nikke/nikke.sqlite3` 和 `data/nikke/secret.key`。密钥应保持 `600` 权限，丢失后旧 Cookie 无法恢复，只能让用户重新绑定。

## 测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖令牌超时与单次消费、Cookie 加密、来源过滤、跨站 CORS、账号隔离基础行为、`game_openid`/正式 `intl_openid` 恢复、AEL 计算和 25 人汇总卡。模拟测试不能替代授权账号的真实端到端验收。

## 许可证与来源

本项目采用 GPL-3.0-or-later。部分 API 适配和算法基于
[ExiaProject/ExiaInvasion](https://github.com/ExiaProject/ExiaInvasion) 移植，详见 `NOTICE`。
