import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import svgr from "vite-plugin-svgr";

export default defineConfig(({ mode }) => {
  const envDir = path.resolve(import.meta.dirname, "../..");
  const env = { ...loadEnv(mode, envDir, ""), ...process.env };
  const host = env.WEB_HOST ?? "127.0.0.1";
  const port = Number(env.WEB_PORT ?? "5173");
  const target = env.API_PROXY_TARGET ?? "http://127.0.0.1:8080";
  if (!host.trim()) throw new Error("WEB_HOST no puede estar vacío");
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("WEB_PORT debe ser un entero entre 1 y 65535");
  }
  const url = new URL(target);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
    throw new Error("API_PROXY_TARGET debe ser una URL HTTP sin credenciales");
  }
  return {
    envDir,
    plugins: [react(), svgr(), tailwindcss(), babel({ presets: [reactCompilerPreset()] })],
    resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
    server: {
      host, port, strictPort: true,
      proxy: { "/api": { target, rewrite: (route) => route.replace(/^\/api/, "") } },
    },
  };
});
