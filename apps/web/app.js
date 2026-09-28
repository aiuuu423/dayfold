import { createApiClient } from "./api-client.js";
import { getAuthClient } from "./auth-client.js";
import { createAuthView } from "./auth-ui.js";
import { publicConfig } from "./public-config.js";

const state = {
  conversationId: null,
  activeView: "today",
  authenticated: false,
  verifyEmailActivation: null,
};

const elements = {
  sessionLoading: document.querySelector("#session-loading"),
  loginView: document.querySelector("#login-view"),
  loginForm: document.querySelector("#login-form"),
  loginUsername: document.querySelector("#login-username"),
  loginPassword: document.querySelector("#login-password"),
  showActivation: document.querySelector("#show-activation"),
  activationForm: document.querySelector("#activation-form"),
  activationEmail: document.querySelector("#activation-email"),
  activationUsername: document.querySelector("#activation-username"),
  activationPassword: document.querySelector("#activation-password"),
  activationVerifyForm: document.querySelector("#activation-verify-form"),
  activationCode: document.querySelector("#activation-code"),
  authError: document.querySelector("#auth-error"),
  appShell: document.querySelector("#app-shell"),
  signOut: document.querySelector("#sign-out"),
  views: [...document.querySelectorAll("[data-view]")],
  navButtons: [...document.querySelectorAll("[data-view-target]")],
  todayDate: document.querySelector("#today-date"),
  entryForm: document.querySelector("#entry-form"),
  entryContent: document.querySelector("#entry-content"),
  entryStatus: document.querySelector("#entry-status"),
  entryCount: document.querySelector("#entry-count"),
  entriesList: document.querySelector("#entries-list"),
  newConversation: document.querySelector("#new-conversation"),
  chatEmpty: document.querySelector("#chat-empty"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  messageList: document.querySelector("#message-list"),
  memoryList: document.querySelector("#memory-list"),
  growthContent: document.querySelector("#growth-content"),
  toast: document.querySelector("#toast"),
};

function formatDate(value, options = {}) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    ...options,
  }).format(new Date(value));
}

function setTodayDate() {
  elements.todayDate.textContent = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 3200);
}

const authClient = getAuthClient();

function clearPrivateViewState() {
  state.conversationId = null;
  elements.entryContent.value = "";
  elements.chatInput.value = "";
  elements.entriesList.replaceChildren();
  elements.messageList.replaceChildren();
  elements.memoryList.replaceChildren();
  elements.growthContent.replaceChildren();
  elements.entryCount.textContent = "";
  elements.chatEmpty.hidden = false;
}

const authView = createAuthView(
  elements,
  () => {
    state.authenticated = false;
    clearPrivateViewState();
  },
  showToast,
);

const apiClient = createApiClient({
  origin: publicConfig.apiOrigin,
  getAccessToken: () => authClient.getAccessToken(),
  onUnauthorized: async () => {
    try {
      await authClient.signOut();
    } catch {
      // 本地 UI 仍然按未认证处理，服务端已经拒绝当前 token。
    }
    authView.showLogin("会话已失效，请重新登录。");
  },
  onUnavailable: (error) => {
    authView.showUnavailable(error.message);
  },
});

const api = (path, options) => apiClient.request(path, options);

function emptyLine(message) {
  const paragraph = document.createElement("p");
  paragraph.className = "empty-state";
  paragraph.textContent = message;
  return paragraph;
}

function setView(viewName) {
  state.activeView = viewName;
  elements.views.forEach((view) => {
    const active = view.dataset.view === viewName;
    view.hidden = !active;
    view.classList.toggle("is-active", active);
  });
  elements.navButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewTarget === viewName);
  });
  if (viewName === "today") loadEntries();
  if (viewName === "memories") loadMemories();
  if (viewName === "growth") loadGrowth();
}

function createEntryElement(entry) {
  const article = document.createElement("article");
  article.className = "entry-item";

  const meta = document.createElement("div");
  meta.className = "entry-meta";
  const date = document.createElement("span");
  date.textContent = formatDate(entry.occurred_at, {
    hour: "2-digit",
    minute: "2-digit",
  });
  const version = document.createElement("span");
  version.textContent = `第 ${entry.version} 版`;
  meta.append(date, version);

  const editor = document.createElement("textarea");
  editor.className = "entry-body";
  editor.value = entry.content;
  editor.setAttribute("aria-label", "编辑日记内容");

  const actions = document.createElement("div");
  actions.className = "entry-actions";
  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "保存修改";
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await api(`/v1/entries/${entry.id}`, {
        method: "PATCH",
        headers: { "If-Match": String(entry.version) },
        body: JSON.stringify({ content: editor.value }),
      });
      showToast("记录已更新");
      await loadEntries();
    } catch (error) {
      showToast(error.message);
    } finally {
      save.disabled = false;
    }
  });
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger";
  remove.textContent = "删除";
  remove.addEventListener("click", async () => {
    remove.disabled = true;
    try {
      await api(`/v1/entries/${entry.id}`, { method: "DELETE" });
      showToast("记录已删除");
      await loadEntries();
    } catch (error) {
      showToast(error.message);
      remove.disabled = false;
    }
  });
  actions.append(save, remove);
  article.append(meta, editor, actions);
  return article;
}

async function loadEntries() {
  elements.entriesList.replaceChildren(emptyLine("正在翻阅记录……"));
  try {
    const payload = await api("/v1/entries");
    elements.entryCount.textContent = `${payload.items.length} 条`;
    elements.entriesList.replaceChildren(
      ...(payload.items.length
        ? payload.items.map(createEntryElement)
        : [emptyLine("还没有记录。写下第一件值得记住的事。")]),
    );
  } catch (error) {
    elements.entriesList.replaceChildren(emptyLine(error.message));
  }
}

async function createEntry(event) {
  event.preventDefault();
  const button = elements.entryForm.querySelector("button");
  const content = elements.entryContent.value.trim();
  if (!content) return;
  button.disabled = true;
  elements.entryStatus.classList.remove("is-error");
  elements.entryStatus.textContent = "正在保存……";
  try {
    const entry = await api("/v1/entries", {
      method: "POST",
      body: JSON.stringify({
        content,
        occurred_at: new Date().toISOString(),
      }),
    });
    elements.entryContent.value = "";
    elements.entryStatus.textContent = "已保存，正在理解这条记录……";
    const extraction = await api("/v1/memory-extractions", {
      method: "POST",
      body: JSON.stringify({ source_type: "entry", source_id: entry.id }),
    });
    if (extraction.memories.length) {
      await api("/v1/memory-embeddings/sync", { method: "POST" });
      elements.entryStatus.textContent = `已记住 ${extraction.memories.length} 件事`;
    } else {
      elements.entryStatus.textContent = "已保存，没有需要长期记住的内容";
    }
    await loadEntries();
  } catch (error) {
    elements.entryStatus.classList.add("is-error");
    elements.entryStatus.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function appendMessage(role, content = "") {
  elements.chatEmpty.hidden = true;
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = content;
  elements.messageList.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "end" });
  return message;
}

async function ensureConversation() {
  if (state.conversationId) return state.conversationId;
  const conversation = await api("/v1/conversations", {
    method: "POST",
    body: JSON.stringify({ title: "最近的对话" }),
  });
  state.conversationId = conversation.id;
  return conversation.id;
}

async function streamSSE(response, onEvent) {
  if (!response.body) throw new Error("浏览器不支持流式响应。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    blocks.forEach((block) => {
      let eventName = "message";
      let data = null;
      block.split("\n").forEach((line) => {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) data = JSON.parse(line.slice(5).trim());
      });
      if (data) onEvent(eventName, data);
    });
    if (done) break;
  }
}

async function sendChat(event) {
  event.preventDefault();
  const content = elements.chatInput.value.trim();
  if (!content) return;
  const button = elements.chatForm.querySelector("button");
  button.disabled = true;
  elements.chatInput.value = "";
  appendMessage("user", content);
  const assistant = appendMessage("assistant", "");
  assistant.classList.add("is-streaming");
  let userMessageId = null;
  try {
    const conversationId = await ensureConversation();
    const response = await apiClient.fetch(
      `/v1/conversations/${conversationId}/messages/stream`,
      {
        method: "POST",
        headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      },
    );
    await streamSSE(response, (eventName, data) => {
      if (eventName === "message.start") {
        userMessageId = data.user_message_id;
        if (data.recalled_memories?.length) {
          const note = document.createElement("p");
          note.className = "recall-note";
          note.textContent = `想起了 ${data.recalled_memories.length} 条相关记忆`;
          elements.messageList.insertBefore(note, assistant);
        }
      }
      if (eventName === "message.delta") assistant.textContent += data.text;
      if (eventName === "message.error") throw new Error(data.message);
    });
    if (userMessageId) {
      try {
        await api("/v1/memory-extractions", {
          method: "POST",
          body: JSON.stringify({ source_type: "message", source_id: userMessageId }),
        });
      } catch {
        showToast("回复已完成，记忆提取稍后再试");
      }
    }
  } catch (error) {
    assistant.textContent = error.message;
    assistant.classList.add("is-error");
  } finally {
    assistant.classList.remove("is-streaming");
    button.disabled = false;
    elements.chatInput.focus();
  }
}

function createMemoryElement(memory) {
  const article = document.createElement("article");
  article.className = "memory-item";
  article.dataset.status = memory.status;

  const type = document.createElement("span");
  type.className = "memory-type";
  type.textContent = memory.type;

  const body = document.createElement("div");
  const copy = document.createElement("p");
  copy.className = "memory-copy";
  copy.textContent = memory.content;
  const meta = document.createElement("p");
  meta.className = "memory-meta";
  meta.textContent = memory.status === "disabled"
    ? "已关闭，不再参与召回"
    : `置信度 ${Math.round(memory.confidence * 100)}%`;
  body.append(copy, meta);

  const actions = document.createElement("div");
  actions.className = "memory-actions";
  if (memory.status === "active") {
    const disable = document.createElement("button");
    disable.type = "button";
    disable.textContent = "关闭";
    disable.addEventListener("click", async () => {
      disable.disabled = true;
      try {
        await api(`/v1/memories/${memory.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "disabled" }),
        });
        await loadMemories();
      } catch (error) {
        showToast(error.message);
        disable.disabled = false;
      }
    });
    actions.append(disable);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger";
  remove.textContent = "删除";
  remove.addEventListener("click", async () => {
    remove.disabled = true;
    try {
      await api(`/v1/memories/${memory.id}`, { method: "DELETE" });
      await loadMemories();
      showToast("记忆已删除");
    } catch (error) {
      showToast(error.message);
      remove.disabled = false;
    }
  });
  actions.append(remove);
  article.append(type, body, actions);
  return article;
}

async function loadMemories() {
  elements.memoryList.replaceChildren(emptyLine("正在整理记忆……"));
  try {
    const payload = await api("/v1/memories");
    elements.memoryList.replaceChildren(
      ...(payload.items.length
        ? payload.items.map(createMemoryElement)
        : [emptyLine("还没有形成长期记忆。")]),
    );
  } catch (error) {
    elements.memoryList.replaceChildren(emptyLine(error.message));
  }
}

async function loadGrowth() {
  elements.growthContent.replaceChildren(emptyLine("正在回看最近的记录……"));
  try {
    const payload = await api("/v1/growth/current");
    const quote = document.createElement("p");
    quote.className = "growth-quote";
    quote.textContent = payload.content;
    elements.growthContent.replaceChildren(quote);
    if (payload.evidence?.length) {
      const evidence = document.createElement("p");
      evidence.className = "growth-evidence";
      evidence.textContent = `基于 ${payload.evidence.length} 条可追溯记忆`;
      elements.growthContent.append(evidence);
    }
  } catch (error) {
    elements.growthContent.replaceChildren(emptyLine(error.message));
  }
}

async function showApplication() {
  await api("/v1/auth/session");
  state.authenticated = true;
  elements.sessionLoading.hidden = true;
  elements.loginView.hidden = true;
  elements.authError.textContent = "";
  elements.appShell.hidden = false;
  setView(state.activeView);
}

async function submitLogin(event) {
  event.preventDefault();
  const button = elements.loginForm.querySelector("button");
  button.disabled = true;
  elements.authError.textContent = "";
  try {
    const identity = elements.loginUsername.value.trim();
    await authClient.signInWithPassword({
      ...(identity.includes("@") ? { email: identity } : { username: identity }),
      password: elements.loginPassword.value,
    });
    await showApplication();
  } catch (error) {
    if (error.status !== 401) {
      elements.authError.textContent = error.message || "登录失败，请稍后再试。";
    }
  } finally {
    button.disabled = false;
  }
}

function showActivation() {
  elements.authError.textContent = "";
  elements.loginForm.hidden = true;
  elements.showActivation.hidden = true;
  elements.activationForm.hidden = false;
  elements.activationVerifyForm.hidden = true;
  elements.activationEmail.focus();
}

async function submitActivation(event) {
  event.preventDefault();
  const button = elements.activationForm.querySelector("button");
  button.disabled = true;
  elements.authError.textContent = "";
  try {
    state.verifyEmailActivation = await authClient.startEmailActivation({
      email: elements.activationEmail.value.trim(),
      username: elements.activationUsername.value.trim(),
      password: elements.activationPassword.value,
    });
    elements.activationPassword.value = "";
    elements.activationForm.hidden = true;
    elements.activationVerifyForm.hidden = false;
    elements.activationCode.focus();
    showToast("验证码已发送，请查收邮箱。");
  } catch (error) {
    elements.authError.textContent =
      error.message || "暂时无法发送验证码，请稍后再试。";
  } finally {
    button.disabled = false;
  }
}

async function verifyActivation(event) {
  event.preventDefault();
  const button = elements.activationVerifyForm.querySelector("button");
  button.disabled = true;
  elements.authError.textContent = "";
  try {
    if (!state.verifyEmailActivation) {
      throw new Error("激活流程已过期，请重新发送验证码。");
    }
    await state.verifyEmailActivation(elements.activationCode.value.trim());
    state.verifyEmailActivation = null;
    elements.activationCode.value = "";
    await showApplication();
  } catch (error) {
    elements.authError.textContent =
      error.message || "验证码无效或已过期，请重试。";
  } finally {
    button.disabled = false;
  }
}

async function signOut() {
  elements.signOut.disabled = true;
  try {
    await authClient.signOut();
  } catch (error) {
    showToast(error.message || "退出失败，请稍后再试。");
    elements.signOut.disabled = false;
    return;
  }
  authView.showLogin();
  elements.signOut.disabled = false;
}

async function restoreSession() {
  try {
    const session = await authClient.getSession();
    if (!session) {
      authView.showLogin();
      return;
    }
    await showApplication();
  } catch (error) {
    if (error.status !== 401) {
      elements.sessionLoading.hidden = true;
      elements.loginView.hidden = false;
      elements.authError.textContent =
        error.message || "暂时无法恢复会话，请稍后重试。";
    }
  }
}

elements.navButtons.forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewTarget));
});
elements.entryForm.addEventListener("submit", createEntry);
elements.chatForm.addEventListener("submit", sendChat);
elements.loginForm.addEventListener("submit", submitLogin);
elements.showActivation.addEventListener("click", showActivation);
elements.activationForm.addEventListener("submit", submitActivation);
elements.activationVerifyForm.addEventListener("submit", verifyActivation);
elements.signOut.addEventListener("click", signOut);
elements.newConversation.addEventListener("click", () => {
  state.conversationId = null;
  elements.messageList.replaceChildren();
  elements.chatEmpty.hidden = false;
  showToast("已开始一段新对话");
});
document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    elements.chatInput.value = button.dataset.prompt;
    elements.chatInput.focus();
  });
});

authClient.onAuthStateChange((event, session) => {
  if (event === "SIGNED_OUT") {
    authView.showLogin();
  }
  if (
    session &&
    ["INITIAL_SESSION", "SIGNED_IN", "TOKEN_REFRESHED"].includes(event)
  ) {
    elements.authError.textContent = "";
  }
});

setTodayDate();
restoreSession();
