import assert from "node:assert/strict";
import test from "node:test";

import { createAuthClientFactory } from "../auth-client-core.js";

function cloudBaseFixture() {
  let session = { access_token: "token-one" };
  const events = [];
  const calls = { init: 0, signIn: [], signOut: 0 };
  const auth = {
    async getSession() {
      return { data: { session }, error: null };
    },
    async signInWithPassword(credentials) {
      calls.signIn.push(credentials);
      return { data: { session }, error: null };
    },
    async signOut() {
      calls.signOut += 1;
      session = null;
      return { error: null };
    },
    onAuthStateChange(listener) {
      events.push(listener);
      return { data: { subscription: { unsubscribe() {} } } };
    },
  };
  const sdk = {
    init(config) {
      calls.init += 1;
      calls.config = config;
      return { auth };
    },
  };
  return {
    sdk,
    calls,
    events,
    setSession(value) {
      session = value;
    },
  };
}

test("CloudBase app 和 auth 在重复获取客户端时只初始化一次", () => {
  const fixture = cloudBaseFixture();
  const getClient = createAuthClientFactory(fixture.sdk.init);
  const config = {
    env: "dayfold-test",
    region: "ap-shanghai",
  };

  const first = getClient(config);
  const second = getClient(config);

  assert.equal(first, second);
  assert.equal(fixture.calls.init, 1);
  assert.deepEqual(fixture.calls.config, {
    ...config,
    auth: { detectSessionInUrl: false },
  });
});

test("认证客户端支持邮箱密码登录、会话恢复和退出", async () => {
  const fixture = cloudBaseFixture();
  const client = createAuthClientFactory(fixture.sdk.init)({
    env: "dayfold-test",
    region: "ap-shanghai",
  });

  assert.deepEqual(await client.getSession(), { access_token: "token-one" });
  await client.signInWithPassword({
    email: "invited@example.com",
    password: "not-a-real-secret",
  });
  assert.deepEqual(fixture.calls.signIn, [
    { email: "invited@example.com", password: "not-a-real-secret" },
  ]);
  assert.equal(await client.getAccessToken(), "token-one");

  await client.signOut();
  assert.equal(fixture.calls.signOut, 1);
  assert.equal(await client.getAccessToken(), null);
});

test("认证客户端传递会话事件并始终读取刷新后的 token", async () => {
  const fixture = cloudBaseFixture();
  const client = createAuthClientFactory(fixture.sdk.init)({
    env: "dayfold-test",
    region: "ap-shanghai",
  });
  const received = [];

  client.onAuthStateChange((event, session) => received.push({ event, session }));
  fixture.events[0]("INITIAL_SESSION", { access_token: "token-one" });
  fixture.events[0]("SIGNED_IN", { access_token: "token-one" });
  fixture.setSession({ access_token: "token-two" });
  fixture.events[0]("TOKEN_REFRESHED", { access_token: "token-two" });
  fixture.events[0]("SIGNED_OUT", null);

  assert.deepEqual(
    received.map(({ event }) => event),
    ["INITIAL_SESSION", "SIGNED_IN", "TOKEN_REFRESHED", "SIGNED_OUT"],
  );
  assert.equal(await client.getAccessToken(), "token-two");
});

test("CloudBase 返回 error 时认证方法拒绝而不是伪装成功", async () => {
  const error = new Error("invalid credentials");
  const getClient = createAuthClientFactory(() => ({
    auth: {
      getSession: async () => ({ data: null, error }),
      signInWithPassword: async () => ({ data: null, error }),
      signOut: async () => ({ error }),
      onAuthStateChange() {},
    },
  }));
  const client = getClient({ env: "test", region: "ap-shanghai" });

  await assert.rejects(client.getSession(), error);
  await assert.rejects(
    client.signInWithPassword({ email: "a@example.com", password: "bad" }),
    error,
  );
  await assert.rejects(client.signOut(), error);
});
