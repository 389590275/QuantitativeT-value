import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const root = path.resolve(__dirname, "..");
  const env = loadEnv(mode, root, "");
  const apiHost = env.API_HOST || "127.0.0.1";
  const apiPort = env.API_PORT || "10002";
  const apiOrigin = `http://${apiHost}:${apiPort}`;

  return {
    plugins: [react()],
    envDir: root,
    define: {
      __API_HOST__: JSON.stringify(apiHost),
      __API_PORT__: JSON.stringify(apiPort),
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiOrigin,
          changeOrigin: true,
        },
        // WebSocket 开发环境直连后端，不走代理，避免 ECONNABORTED
      },
    },
  };
});
