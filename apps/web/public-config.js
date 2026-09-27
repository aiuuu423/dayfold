// 这里的值会进入浏览器构建产物，只能配置 CloudBase 公开客户端信息。
export const publicConfig = Object.freeze({
  apiOrigin:
    import.meta.env.VITE_DAYFOLD_API_ORIGIN || "https://dayfold-api-global.vercel.app",
  cloudbase: Object.freeze({
    env: import.meta.env.VITE_CLOUDBASE_ENV_ID || "",
    region: import.meta.env.VITE_CLOUDBASE_REGION || "ap-shanghai",
  }),
});
