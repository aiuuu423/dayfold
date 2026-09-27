function unwrap(result) {
  if (result?.error) {
    throw result.error;
  }
  return result?.data ?? null;
}

export function createAuthClientFactory(initialize) {
  let client;

  return (config) => {
    if (client) return client;

    const app = initialize({
      env: config.env,
      region: config.region,
      auth: { detectSessionInUrl: false },
    });
    const auth = app.auth;

    client = Object.freeze({
      async getSession() {
        const data = unwrap(await auth.getSession());
        return data?.session ?? null;
      },

      async getAccessToken() {
        const data = unwrap(await auth.getSession());
        return data?.session?.access_token ?? null;
      },

      async signInWithPassword(credentials) {
        return unwrap(await auth.signInWithPassword(credentials));
      },

      async signOut() {
        return unwrap(await auth.signOut());
      },

      onAuthStateChange(listener) {
        return auth.onAuthStateChange(listener);
      },
    });

    return client;
  };
}
