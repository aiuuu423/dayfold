import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const webRoot = new URL("../", import.meta.url);

test("页面提供会话恢复、密码登录、受邀账号激活和退出控件", async () => {
  const html = await readFile(new URL("index.html", webRoot), "utf8");

  assert.match(html, /id="session-loading"/);
  assert.match(html, /id="login-view"/);
  assert.match(html, /id="login-form"/);
  assert.match(html, /id="login-username"[^>]*autocomplete="username"/s);
  assert.match(html, /id="login-password"[^>]*type="password"/s);
  assert.match(html, /id="auth-error"[^>]*aria-live="polite"/s);
  assert.match(html, /id="show-activation"/);
  assert.match(html, /id="activation-form"/);
  assert.match(html, /id="activation-email"[^>]*type="email"/s);
  assert.match(html, /id="activation-username"/);
  assert.match(html, /id="activation-password"[^>]*type="password"/s);
  assert.match(html, /id="activation-verify-form"/);
  assert.match(html, /id="activation-code"[^>]*autocomplete="one-time-code"/s);
  assert.match(html, /id="sign-out"/);
});

test("生产页面不再提供 API Origin 设置或 Demo 状态", async () => {
  const [html, app] = await Promise.all([
    readFile(new URL("index.html", webRoot), "utf8"),
    readFile(new URL("app.js", webRoot), "utf8"),
  ]);

  assert.doesNotMatch(html, /api-origin|settings-dialog|Demo only|synthetic data/i);
  assert.doesNotMatch(app, /localStorage|\/v1\/demo|openSettings/);
});

test("公开配置只使用浏览器可公开的 Vite 变量", async () => {
  const config = await readFile(new URL("public-config.js", webRoot), "utf8");

  assert.match(config, /VITE_CLOUDBASE_ENV_ID/);
  assert.match(config, /VITE_CLOUDBASE_REGION/);
  assert.match(config, /VITE_CLOUDBASE_PUBLISHABLE_KEY/);
  assert.match(config, /VITE_DAYFOLD_API_ORIGIN/);
  assert.doesNotMatch(config, /SECRET|REFRESH_TOKEN|SERVER_API_KEY/);
});

test("生产 CSP 只允许 Dayfold API 和 CloudBase Gateway 连接", async () => {
  const vercelConfig = JSON.parse(
    await readFile(new URL("vercel.json", webRoot), "utf8"),
  );
  const csp = vercelConfig.headers[0].headers.find(
    ({ key }) => key === "Content-Security-Policy",
  ).value;
  const connectSrc = csp.match(/connect-src ([^;]+)/)?.[1] || "";

  assert.match(connectSrc, /'self'/);
  assert.match(connectSrc, /https:\/\/dayfold-api-global\.vercel\.app/);
  assert.match(connectSrc, /https:\/\/\*\.api\.tcloudbasegateway\.com/);
  assert.match(connectSrc, /https:\/\/\*\.tcb-api\.tencentcloudapi\.com/);
  assert.doesNotMatch(connectSrc, /(?:^|\s)http:(?:\s|$)/);
  assert.doesNotMatch(connectSrc, /(?:^|\s)https:(?:\s|$)/);
});

test("Web 开发与部署配置使用 apps/web 下的 Vite 环境文件", async () => {
  const [packageJson, envExample, gitignore] = await Promise.all([
    readFile(new URL("package.json", webRoot), "utf8").then(JSON.parse),
    readFile(new URL(".env.example", webRoot), "utf8"),
    readFile(new URL(".gitignore", webRoot), "utf8"),
  ]);

  assert.equal(packageJson.scripts.dev, "vite");
  assert.equal(packageJson.scripts.preview, "vite preview");
  assert.match(envExample, /VITE_DAYFOLD_API_ORIGIN=/);
  assert.match(envExample, /VITE_CLOUDBASE_ENV_ID=/);
  assert.match(envExample, /VITE_CLOUDBASE_PUBLISHABLE_KEY=/);
  assert.doesNotMatch(envExample, /SERVER_API_KEY|SECRET|REFRESH_TOKEN/);
  assert.match(gitignore, /!\.env\.example/);
});
