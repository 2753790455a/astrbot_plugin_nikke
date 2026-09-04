// SPDX-License-Identifier: GPL-3.0-or-later
// 只观察 BlaBlaLink API 请求中的账号上下文头，不读取请求体或响应内容。
chrome.webRequest.onBeforeSendHeaders.addListener(
  async (details) => {
    const headers = details.requestHeaders || [];
    const common = headers.find((item) => item.name.toLowerCase() === "x-common-params");
    if (!common?.value) return;
    try {
      const parsed = JSON.parse(common.value);
      if (parsed && typeof parsed === "object" && parsed.openid) {
        await chrome.storage.local.set({ xCommonParams: common.value });
      }
    } catch {
      // 非JSON或不完整请求头不保存，等待官网后续完整请求。
    }
  },
  // 新版官网会先从多个 BlaBlaLink 子域发起请求，不能只监听 api 子域。
  { urls: ["https://*.blablalink.com/*"] },
  ["requestHeaders", "extraHeaders"]
);
