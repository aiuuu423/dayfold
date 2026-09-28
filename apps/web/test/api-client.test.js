import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, createApiClient } from "../api-client.js";

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("普通 API 请求在每次发送前注入当前 Bearer Token", async () => {
  let token = "token-one";
  const requests = [];
  const client = createApiClient({
    origin: "https://api.example.com",
    getAccessToken: async () => token,
    fetchImpl: async (url, options) => {
      requests.push({ url, options });
      return jsonResponse(200, { ok: true });
    },
  });

  await client.request("/v1/entries");
  token = "token-two";
  await client.request("/v1/memories", { method: "POST", body: "{}" });

  assert.equal(requests[0].options.headers.get("Authorization"), "Bearer token-one");
  assert.equal(requests[1].options.headers.get("Authorization"), "Bearer token-two");
  assert.equal(requests[1].options.headers.get("Content-Type"), "application/json");
});

test("Chat SSE 请求使用同一个认证请求入口和 Bearer Token", async () => {
  let captured;
  const response = new Response("event: message.delta\ndata: {\"text\":\"好\"}\n\n");
  const client = createApiClient({
    origin: "https://api.example.com",
    getAccessToken: async () => "stream-token",
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return response;
    },
  });

  const result = await client.fetch("/v1/conversations/c1/messages/stream", {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    body: "{\"content\":\"你好\"}",
  });

  assert.equal(result, response);
  assert.equal(captured.url, "https://api.example.com/v1/conversations/c1/messages/stream");
  assert.equal(captured.options.headers.get("Authorization"), "Bearer stream-token");
  assert.equal(captured.options.headers.get("Accept"), "text/event-stream");
});

test("401 触发退出回调并保留后端通用错误", async () => {
  let unauthorized = 0;
  let unavailable = 0;
  const client = createApiClient({
    origin: "https://api.example.com",
    getAccessToken: async () => "expired",
    fetchImpl: async () =>
      jsonResponse(401, { error: { code: "INVALID_TOKEN", message: "请重新登录" } }),
    onUnauthorized: async () => {
      unauthorized += 1;
    },
    onUnavailable: () => {
      unavailable += 1;
    },
  });

  await assert.rejects(
    client.request("/v1/entries"),
    (error) =>
      error instanceof ApiError &&
      error.status === 401 &&
      error.code === "INVALID_TOKEN" &&
      error.message === "请重新登录",
  );
  assert.equal(unauthorized, 1);
  assert.equal(unavailable, 0);
});

test("503 仅显示服务不可用，不清理认证会话", async () => {
  let unauthorized = 0;
  let unavailable = 0;
  const client = createApiClient({
    origin: "https://api.example.com",
    getAccessToken: async () => "valid",
    fetchImpl: async () =>
      jsonResponse(503, {
        error: { code: "AUTH_PROVIDER_UNAVAILABLE", message: "认证服务暂时不可用" },
      }),
    onUnauthorized: () => {
      unauthorized += 1;
    },
    onUnavailable: ({ status }) => {
      unavailable += status;
    },
  });

  await assert.rejects(client.request("/v1/entries"), ApiError);
  assert.equal(unauthorized, 0);
  assert.equal(unavailable, 503);
});

test("没有会话时不发送伪造 Authorization 值", async () => {
  let headers;
  const client = createApiClient({
    origin: "https://api.example.com",
    getAccessToken: async () => null,
    fetchImpl: async (_url, options) => {
      headers = options.headers;
      return jsonResponse(401, { detail: "Unauthorized" });
    },
  });

  await assert.rejects(client.request("/v1/entries"), ApiError);
  assert.equal(headers.has("Authorization"), false);
});
