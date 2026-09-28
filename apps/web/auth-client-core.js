function unwrap(result) {
  if (result?.error) {
    throw result.error;
  }
  return result?.data ?? null;
}

function isMissingCredentials(error) {
  return error?.message?.toLowerCase().includes("credentials not found");
}

async function readSession(auth) {
  const result = await auth.getSession();
  if (isMissingCredentials(result?.error)) {
    return null;
  }
  const data = unwrap(result);
  return data?.session ?? null;
}

export function createAuthClientFactory(initialize) {
  let client;

  return (config) => {
    if (client) return client;

    const app = initialize({
      env: config.env,
      region: config.region,
      accessKey: config.publishableKey,
      auth: { detectSessionInUrl: false },
    });
    const auth = app.auth;

    client = Object.freeze({
      async getSession() {
        return readSession(auth);
      },

      async getAccessToken() {
        const session = await readSession(auth);
        return session?.access_token ?? null;
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
