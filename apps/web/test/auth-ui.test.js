import assert from "node:assert/strict";
import test from "node:test";

import { createAuthView } from "../auth-ui.js";

function elementsFixture() {
  return {
    sessionLoading: { hidden: false },
    loginView: { hidden: true },
    authError: { textContent: "" },
    loginPassword: { value: "secret" },
    loginEmail: { focusCalls: 0, focus() { this.focusCalls += 1; } },
    appShell: { hidden: false },
  };
}

test("401 视图切换会清理私有页面状态并返回登录页", () => {
  const elements = elementsFixture();
  let resets = 0;
  const view = createAuthView(elements, () => {
    resets += 1;
  });

  view.showLogin("会话已失效，请重新登录。");

  assert.equal(resets, 1);
  assert.equal(elements.sessionLoading.hidden, true);
  assert.equal(elements.appShell.hidden, true);
  assert.equal(elements.loginView.hidden, false);
  assert.equal(elements.loginPassword.value, "");
  assert.equal(elements.authError.textContent, "会话已失效，请重新登录。");
  assert.equal(elements.loginEmail.focusCalls, 1);
});

test("503 维护状态保留已登录应用和页面内容", () => {
  const elements = elementsFixture();
  let resets = 0;
  const view = createAuthView(elements, () => {
    resets += 1;
  });

  view.showUnavailable("认证服务暂时不可用");

  assert.equal(resets, 0);
  assert.equal(elements.appShell.hidden, false);
  assert.equal(elements.loginView.hidden, true);
  assert.equal(elements.authError.textContent, "");
});
