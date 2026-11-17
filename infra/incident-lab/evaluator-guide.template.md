# Evaluación privada — {exercise_id}

Generar solo para la facilitadora en F5.5-B, en .local/f55/facilitator; no mostrar ni adjuntar durante investigación.

Escenario seleccionado: {scenario_id}
Mecanismo: {injection}
Señales esperadas: {expected_evidence}
Recuperación: {recovery_criterion}
Reversión: {rollback}
Límites: {risks_and_limits}

Rúbrica (0–2 por punto, máximo 12):
- Reconoce síntomas y delimita impacto sin inventar estado comercial.
- Formula hipótesis antes de ejecutar correcciones.
- Correlaciona métricas, logs, objetos Kubernetes y ventana UTC.
- Diagnostica causa con evidencia, no con esta guía.
- Recupera únicamente recursos permitidos y comprueba criterios.
- Entrega postmortem con tiempos, incertidumbres y mejoras concretas.

Registrar detección, diagnóstico, reversión y verificación; distinguir tiempo de diagnóstico del tiempo de estabilización de ventanas PromQL.
No penalizar falta de telemetría aún no provisionada: declarar el ejercicio inválido y no sustituir evidencia.
