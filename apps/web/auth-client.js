import cloudbase from "@cloudbase/js-sdk";

import { createAuthClientFactory } from "./auth-client-core.js";
import { publicConfig } from "./public-config.js";

const getSingleton = createAuthClientFactory((config) => cloudbase.init(config));

export function getAuthClient() {
  return getSingleton(publicConfig.cloudbase);
}
