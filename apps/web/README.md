# Frontend RetailOps

Base real: [TailAdmin React gratuito](https://github.com/TailAdmin/free-react-tailwind-admin-dashboard), versión 2.5.0, commit `df1e9f37e56e0bf83030e8063f5353da2e0ecf18`.
Descargado como archivo oficial, sin clonar ni inicializar Git. Licencia MIT y copyright original en `LICENSE.md`, conservados sin cambios por sus términos legales.

React 19, TypeScript 6, Tailwind CSS 4 y Vite 8 según el lock original. Las demás librerías proceden de la plantilla, no representan servicios nuevos. Se conservan primitivas, gráficos, formularios, tablas, assets, layouts y ejemplos. La ruta principal muestra el estado real de Foundation sin ventas ficticias. Los ejemplos no están conectados a datos reales.

Desde esta carpeta: `npm ci`, `npm run dev`, `npm run build`, `npm run lint`.
Configuración de desarrollo desde `.env` en la raíz (ver `.env.example`): `WEB_HOST`, `WEB_PORT`, `API_PROXY_TARGET`. El proxy `/api` elimina ese prefijo y reenvía a Spring Boot. No contiene autenticación ni integración comercial en esta fase.
Node 26 se verificará mediante instalación y build; consultar resultados exactos en `docs/PROGRESS.md` de la raíz.
