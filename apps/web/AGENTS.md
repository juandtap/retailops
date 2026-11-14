# Frontend RetailOps sobre TailAdmin

Leer primero el AGENTS.md de la raíz. Base oficial gratuita TailAdmin; conservar licencia MIT y componentes reutilizables.
- Rutas: `src/App.tsx`; navegación: `src/components/layout/app-layout/sidebar/data.tsx`.
- Mantener AppLayout, SidebarProvider, estilos Tailwind v4 (`src/index.css`) y variantes responsive/oscuro.
- Importar componentes de `src/components/ui` directamente y enlaces desde `react-router`.
- Texto nuevo mediante `useTranslations` de `@/i18n`; agregar claves a los cuatro archivos `src/messages/*.json` (contenido propio en español).
- No instalar otra librería de UI ni implementar autenticación en Fase 0.
- Ejecutar `npm run build` y `npm run lint` después de cambios. Registrar fallos heredados por separado.
- Las páginas de demostración conservadas son ejemplos de TailAdmin, no capacidades implementadas de RetailOps.
