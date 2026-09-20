const HEALTH_CONTRACT = Object.freeze({
  status: "ok",
  service: "dayfold-api",
  environment: "preview",
  version: "p1-probe",
});

const STORAGE_KEY = "dayfold-preview-api-origin";
const REQUEST_TIMEOUT_MS = 10_000;

const form = document.querySelector("#probe-form");
const input = document.querySelector("#api-origin");
const button = document.querySelector("#check-button");
const statusPanel = document.querySelector("#status");
const statusLabel = statusPanel.querySelector(".status-label");
const statusMessage = document.querySelector("#status-message");
const healthDetails = document.querySelector("#health-details");

const detailFields = {
  status: document.querySelector("#health-status"),
  service: document.querySelector("#health-service"),
  environment: document.querySelector("#health-environment"),
  version: document.querySelector("#health-version"),
};

function normalizeOrigin(value) {
  const url = new URL(value.trim());

  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("unsupported-protocol");
  }

  return url.origin;
}

function matchesHealthContract(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    Object.entries(HEALTH_CONTRACT).every(
      ([key, expectedValue]) => payload[key] === expectedValue,
    )
  );
}

function setState(state, message, payload = null) {
  const labels = {
    idle: "等待检查",
    loading: "正在连接",
    success: "连接正常",
    error: "检查失败",
  };

  statusPanel.dataset.state = state;
  statusLabel.textContent = labels[state];
  statusMessage.textContent = message;
  button.disabled = state === "loading";
  button.textContent = state === "loading" ? "检查中…" : "检查 API";

  const showDetails = state === "success" && payload;
  healthDetails.hidden = !showDetails;

  if (showDetails) {
    Object.entries(detailFields).forEach(([key, element]) => {
      element.textContent = payload[key];
    });
  }
}

function restoreOrigin() {
  const queryOrigin = new URLSearchParams(window.location.search).get("api");
  let savedOrigin = "";

  try {
    savedOrigin = window.localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    savedOrigin = "";
  }

  const initialValue = queryOrigin || savedOrigin;
  if (!initialValue) {
    return;
  }

  try {
    input.value = normalizeOrigin(initialValue);
  } catch {
    setState("error", "预填地址无效，请输入完整的 http 或 https 地址。");
  }
}

async function checkHealth(origin) {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS,
  );

  try {
    const response = await fetch(`${origin}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error("http-error");
    }

    const payload = await response.json();
    if (!matchesHealthContract(payload)) {
      throw new Error("contract-error");
    }

    return payload;
  } finally {
    window.clearTimeout(timeout);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  let origin;
  try {
    origin = normalizeOrigin(input.value);
  } catch {
    setState("error", "请输入完整的 http 或 https API 地址。");
    input.focus();
    return;
  }

  input.value = origin;
  try {
    window.localStorage.setItem(STORAGE_KEY, origin);
  } catch {
    // 本地存储不可用不会阻断当前连通性检查。
  }

  setState("loading", "正在请求 /health，最长等待 10 秒。");

  try {
    const payload = await checkHealth(origin);
    setState("success", "静态页面已成功读取 FastAPI 健康响应。", payload);
  } catch (error) {
    const message =
      error.name === "AbortError"
        ? "请求超过 10 秒，请检查 API 是否可访问。"
        : "无法确认 API 状态，请检查地址、HTTPS 与 CORS 配置。";
    setState("error", message);
  }
});

restoreOrigin();
