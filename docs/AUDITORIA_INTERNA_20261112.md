# SYPC Swap — registro de auditoría interna focal (12/11/2026)

**Estado:** revisión técnica interna sobre una rama aislada, sin despliegue ni garantía de aptitud para dinero real.  
**Base:** `review/security-cleanup-consistency-20261112` @ `837440f403e873aea8620f058d3c2b31997da2e7`.  
**Propuesta:** `audit/security-hardening-p0-20261112` / PR #18. Mantener en **draft**.

## Alcance y límites

Se han revisado la arquitectura, contratos candidatos ErgoScript y pruebas Scala/Sigma, módulos Python de modelado/preflight, herramientas auxiliares, manifests de terceros, workflows, políticas de publicación y ensayos. Este proceso no representa una auditoría formal completa de los miles de líneas del código de terceros ni del núcleo SYPC. No se han accedido a los nodos domésticos o wallets ni se han construido transacciones completas en la cadena privada.

**Pruebas Python y Sigma son capas distintas:** un PASS no implica que una transacción entera sea válida ante el consenso SYPC, que un reembolso siempre pueda ejecutarse ni que la red privada esté aislada de Internet.

## Hallazgos y decisiones

| ID | Prioridad | Hallazgo | Tratamiento | Estado |
| --- | --- | --- | --- | --- |
| QA-01 | P0 | Los siete tests Sigma solo se repetían en workflows de ramas antiguas; la rama nueva pasaba CI Python sin ejecución de contratos | Crear gate `security-sigma-current.yml` para las siete suites en cada PR, dos runners Java 11 | Implementado; gate independiente de consenso |
| QA-02 | P1 | Ejecutar varias suites Sigma juntas genera colisiones esporádicas del estado `_sourceContext` del compilador | Una ejecución sbt/JVM independiente **por suite**; mínimo de casos históricos exigido; cancelar runs de PR obsoletos | Implementado; validar CI definitivo |
| QA-03 | P0 | Dos nodos de una cadena equivocada podían coincidir entre sí y producir un PASS de consistencia | Requerir `--expected-genesis-id` fijado desde el manifiesto del propietario, no desde nodos | Implementado en herramienta offline; verificación en nodos pendiente |
| QA-04 | P1 | `os.open(O_RDONLY)` sobre una FIFO puede bloquear antes de comprobar el tipo de archivo | `O_NONBLOCK`, `O_NOFOLLOW` y descriptor cerrado; test FIFO sin escritor | Implementado y probado offline |
| QA-05 | P1 | Solo exigir al menos un par aceptaba conexiones adicionales en la LAN privada de dos nodos | Exigir exactamente uno en cada nodo; **no prueba la identidad ni la IP real** del par | Implementado y pendiente de prueba en LAN |
| QA-06 | P1 | El control YAML permitía variantes de eventos privilegiados inline y overrides por trabajo | Rechazo conservador de eventos elevados inline y cualquier override `permissions` por job | Implementado y probado offline |
| QA-07 | P1 | `upstreams.lock.json` y `third_party/REFERENCES.json` se validaban por separado | Rechazar revisiones/licencias discordantes y URLs de origen duplicadas | Implementado y probado offline |
| QA-08 | P1 | API de ejemplo `wallet_cancel_refund_preflight` permisiva en el paquete, distinta de contratos estrictos | Retirar el helper inseguro; conservar comprobación de rama heredada y tests del preflight estricto | Implementado, pruebas actualizadas |
| QA-09 | P2 | Cinco workflows de laboratorio repetidos y atados a ramas históricas | Retirar del árbol activo; versiones y ejecuciones anteriores conservadas en Git | Implementado |
| QA-10 | P0 | Contratos y wallets aún no probados con la transacción completa SYPC, firmas, costes y liveness | Mantener cerrado el paso a fondos reales; [issue #13](https://github.com/sypcoin2026/SYPC-SwaP/issues/13) | **BLOQUEANTE** |
| QA-11 | P0 | Formalización reproducible moderna y revisión externa aún pendientes | [Issue #8](https://github.com/sypcoin2026/SYPC-SwaP/issues/8) | **BLOQUEANTE** |
| QA-12 | P0 | `main` sin reglas verificadas que obliguen a revisión humana y checks | [Issue #6](https://github.com/sypcoin2026/SYPC-SwaP/issues/6) | **BLOQUEANTE** |

## Invariantes que NO se pueden declarar demostrados todavía

- **Consenso:** transacción de orden válida globalmente, aceptación/rechazo de scripts y firmas en el nodo SYPC, coste, UTXO y tarifas.
- **Liveness:** cancelación siempre posible para importes mínimos con/sin sponsor bajo coste y congestión real.
- **Seguridad económica:** precio AMM y redondeos idénticos a la semántica de Sigma/SYPC; protección de LP/reservas y ataques de inicialización.
- **Operación:** REST ligado a loopback, firewall, red P2P realmente aislada, firma solo en wallet y cero secretos en ejecutores, pares independientes.
- **Gobernanza:** reglas obligatorias de revisión de PR, auditoría externa y divulgación responsable realmente activadas.

## Evidencia requerida antes de cerrar este PR

1. Ejecutar controles de procedencia, código offline y todas las suites Python en 3.12 y 3.13, sin fallos.
2. Ejecutar **las siete suites Sigma separadas** en Ubuntu 22.04 y 24.04, demostrar número de pruebas por suite y reproducibilidad.
3. Revisión humana independiente del diff, de los documentos y de los riesgos introducidos. No borrar hallazgos o ejecuciones fallidas del historial.
4. Publicar el SHA exacto de la cabeza y enlaces a CI. **No fusionar automáticamente**.

## Decisión de publicación

- **GO:** investigación, tests y revisiones aisladas sin fondos ni contacto con testnet.
- **NO-GO:** firmar, emitir, ejecutar swaps, desplegar contratos, exponer el backend a Internet o usar carteras reales.
- La próxima prueba en una cadena SYPC descartable requiere autorización posterior, un protocolo de aislamiento y pruebas de consenso propias; no forma parte de este PR.

> La seguridad de SYPCoin no dependerá de que sus desarrolladores sean de confianza, sino de que sus reglas, su código y sus operaciones puedan comprobarse de forma independiente.
