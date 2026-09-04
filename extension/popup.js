// SPDX-License-Identifier: GPL-3.0-or-later
const bindInput = document.getElementById("bindUrl");
const statusBox = document.getElementById("status");

chrome.storage.local.get("bindUrl", ({ bindUrl }) => {
  if (bindUrl) bindInput.value = bindUrl;
});

function parseBindUrl() {
  const url = new URL(bindInput.value.trim());
  if (url.protocol !== "https:" || url.hostname !== "nikke.irises777.xyz") {
    throw new Error("必须使用 nikke.irises777.xyz 的HTTPS绑定链接");
  }
  const match = url.pathname.match(/^\/bind\/([A-Za-z0-9_-]{32,128})$/);
  if (!match) throw new Error("绑定链接格式不正确");
  return { url, token: match[1] };
}

document.getElementById("openLogin").addEventListener("click", async () => {
  try {
    parseBindUrl();
    await chrome.storage.local.set({ bindUrl: bindInput.value.trim() });
    await chrome.tabs.create({ url: "https://www.blablalink.com/login", active: true });
    statusBox.textContent = "请在新标签页完成官网登录和验证码。";
  } catch (error) {
    statusBox.textContent = error.message;
  }
});

document.getElementById("submit").addEventListener("click", async () => {
  statusBox.textContent = "正在读取并验证登录状态…";
  try {
    const { url, token } = parseBindUrl();
    // 与浏览器访问官网时的 Cookie 选择规则保持一致，避免同名跨子域 Cookie 串入。
    const cookies = await chrome.cookies.getAll({ url: "https://www.blablalink.com/" });
    const required = ["game_token", "game_uid", "game_openid"];
    const names = new Set(cookies.map(cookie => cookie.name));
    const missing = required.filter(name => !names.has(name));
    if (missing.length) throw new Error(`尚未完成登录，缺少：${missing.join(", ")}`);
    const response = await fetch(`${url.origin}/api/bind/cookies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, cookies })
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `提交失败 HTTP ${response.status}`);
    await chrome.storage.local.remove("bindUrl");
    statusBox.textContent = `绑定成功：${result.nickname || result.qq_id}\n现在可以关闭或卸载本扩展。`;
  } catch (error) {
    statusBox.textContent = error.message;
  }
});
