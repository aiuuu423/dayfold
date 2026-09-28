export class ApiError extends Error {
  constructor(message, { status, code } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function responseError(response) {
  let payload;
  try {
    payload = await response.clone().json();
  } catch {
    payload = null;
  }

  const detail = payload?.detail;
  const error = payload?.error;
  const message =
    error?.message ||
    (typeof detail === "string" ? detail : detail?.message) ||
    `请求失败（${response.status}）`;
  const code = error?.code || detail?.code;
  return new ApiError(message, { status: response.status, code });
}

export function createApiClient({
  origin,
  getAccessToken,
  fetchImpl = globalThis.fetch,
  onUnauthorized = () => {},
  onUnavailable = () => {},
}) {
  async function authenticatedFetch(path, options = {}) {
    const token = await getAccessToken();
    const headers = new Headers(options.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetchImpl(`${origin}${path}`, { ...options, headers });
    if (response.ok) return response;

    const error = await responseError(response);
    if (response.status === 401) await onUnauthorized(error);
    if (response.status === 503) await onUnavailable(error);
    throw error;
  }

  return Object.freeze({
    fetch: authenticatedFetch,
    async request(path, options) {
      const response = await authenticatedFetch(path, options);
      if (response.status === 204) return null;
      return response.json();
    },
  });
}
