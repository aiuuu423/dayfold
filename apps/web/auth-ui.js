export function createAuthView(elements, resetPrivateState, notify = () => {}) {
  return Object.freeze({
    showLogin(message = "") {
      resetPrivateState();
      elements.sessionLoading.hidden = true;
      elements.appShell.hidden = true;
      elements.loginView.hidden = false;
      elements.authError.textContent = message;
      elements.loginPassword.value = "";
      elements.loginEmail.focus();
    },

    showUnavailable(message = "服务暂时不可用，请稍后再试。") {
      notify(message);
    },
  });
}
