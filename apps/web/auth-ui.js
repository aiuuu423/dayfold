export function createAuthView(elements, resetPrivateState, notify = () => {}) {
  return Object.freeze({
    showLogin(message = "") {
      resetPrivateState();
      elements.sessionLoading.hidden = true;
      elements.appShell.hidden = true;
      elements.loginView.hidden = false;
      if (elements.loginForm) elements.loginForm.hidden = false;
      if (elements.showActivation) elements.showActivation.hidden = false;
      if (elements.activationForm) elements.activationForm.hidden = true;
      if (elements.activationVerifyForm) {
        elements.activationVerifyForm.hidden = true;
      }
      elements.authError.textContent = message;
      elements.loginPassword.value = "";
      elements.loginUsername.focus();
    },

    showUnavailable(message = "服务暂时不可用，请稍后再试。") {
      notify(message);
    },
  });
}
