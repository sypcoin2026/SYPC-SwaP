# Revisión de precedentes y mejoras de seguridad — SYPC Swap
Fecha: 2026-11-12  
Clasificación: **INVESTIGACIÓN / NO-GO para fondos reales**  
Rama de partida: `work/sponsor-refund-guard-20261112` @ `ad0d7a435cb4b9e135d2064c5d277ffa73e3e08d`

## Principio rector

> La seguridad de SYPCoin no dependerá de que sus desarrolladores sean de confianza, sino de que sus reglas, su código y sus operaciones puedan comprobarse de forma independiente.

**Esta investigación no significa que SYPC esté auditada, que los contratos estén desplegados, ni que exista un DEX operativo.**

## 1. Referencias que ya resolvieron partes del problema

| Proyecto / fuente | Qué sirve para estudiar | Limitación relevante | Tratamiento |
| --- | --- | --- | --- |
| [Ergo Contracts](https://github.com/ergoplatform/ergo-contracts) — [intercambio atómico](https://github.com/ergoplatform/ergo-contracts/blob/17ed58b39460e5520de56f615936d918603a3b9e/verified-contracts/src/main/scala/org/ergoplatform/contracts/AssetsAtomicExchange.scala) | Condiciones en cadena para compra/venta, cancelación con firma, propiedades en Stainless y pruebas del compilador | Las propiedades publicadas tienen precondiciones específicas y **no prueban** que nuestro port sea correcto. El toolchain formal histórico no se ha reproducido en la rama actual | Base de propiedad + verificación por repetir, sin adoptar todavía |
| [Spectrum ergo-dex](https://github.com/spectrum-finance/ergo-dex) — ref `8fe94e1f8b4e1ab9402fca6fbc3955e3ad1415f7` | AMM, órdenes, contratos y ejecutores externos que no custodian activos | Historial del repositorio sin pushes desde 2023; `build.sbt` fija `sigma-state 4.0.5` y Scala 2.12.15. No asumir que la aritmética, las dependencias o las firmas son seguras en SYPC | Referencia de diseño, **sin** importar AMM a producción |
| [Lithos Client](https://github.com/Lithos-Protocol/Lithos-Client) y [protocolo](https://lithosprotocol.org/docs/intro) | Pooled mining sin operador, NISPs, pruebas de fraude, límites de tamaños, ventanas de desafío; ejemplos de protección por contratos | Complejidad elevada, liveness condicionado a desafíos y su propio modelo económico. No es un port directo de SYPC Swap ni un remedio al ataque mayoritario PoW | Línea separada para investigación futura de pools SYPC |
| [BasicSwap](https://github.com/basicswap/basicswap) — [criterios de integración](https://docs.basicswapdex.com/docs/user-guides/integrate-coin/) | Intercambio entre blockchains sin custodios ni wrapped tokens, protocolos HTLC/adaptor signatures | La ruta habitual soporta nodos y scripts tipo Bitcoin Core, **no** implica compatibilidad con las transacciones eUTXO de SYPC | Segunda fase externa, prototipo separado sin fondos |
| [Ergo Core](https://github.com/ergoplatform/ergo) | Validación eUTXO y Sigma, red P2P, pruebas de consenso y modelo de estado | Fork != seguridad PoW equivalente. Hace falta potencia minera distribuida y pruebas específicas del estado/consenso SYPC | Reutilizar controles y pruebas, jamás importar parches de consenso sin análisis de aplicabilidad |

La existencia de una prueba formal en upstream **no es un aval de auditoría externa**, ni incluye automáticamente la validez global de transacciones, la economía, los fallos de la cartera o los ataques al consenso.

## 2. Mejoras concretas sobre la base original

### A. Cancelación con devolución verificable (P0)
En los contratos de Ergo Contracts, la ruta de cancelación depende de una firma del dueño y no obliga a que la transacción firmada le devuelva sus activos. Eso es una **propiedad del permiso de firma**, no una falsificación criptográfica. La UX de la cartera jamás debe firmar a ciegas.

Nuestras ramas experimentales [PR #10](https://github.com/sypcoin2026/SYPC-SwaP/pull/10), [PR #11](https://github.com/sypcoin2026/SYPC-SwaP/pull/11) y [PR #12](https://github.com/sypcoin2026/SYPC-SwaP/pull/12) estudian condiciones adicionales:
- Firma legítima y destino de devolución correcto; tokens idénticos a los bloqueados.
- Comisiones acotadas y script de comisión explícito; conservación de nativo con intermedios amplios.
- Patrocinio opcional por otra UTXO del propietario, sin entregar fondos a terceros.

**Límite actual:** las pruebas indicadas en PR #12 (29/29 por entorno) son de Sigma/UTXO sintéticas; no garantizan validez global ni recuperabilidad bajo las reglas reales del nodo SYPC. El patrocinio sólo sirve si hay una UTXO nativa libre y suficientemente financiada.

### B. Demostrar validez de CONSENSO, no sólo de script (P0)
El [issue #13](https://github.com/sypcoin2026/SYPC-SwaP/issues/13) continúa siendo bloqueante. Para declarar éxito hay que registrar simultáneamente:
1. Identidad de red/génesis, versión de ErgoTree y ejecutable SYPC, con hashes exactos.
2. Transacción real completa; entradas y pruebas firmadas; comprobaciones de coste, caja mínima, tasa, activos y estado UTXO del nodo.
3. Observación de inclusión y cambios de estado en dos validadores independientes; evidencia de rechazo de dobles gastos, reorgs y transacciones adversariales.
4. Cancelación posible **antes de bloquear** activos, o rechazo previo de órdenes cuya recuperación no pueda demostrarse bajo hipótesis explicitadas.

Si una de estas condiciones falla, **no habilitar firmas o depósitos**. Nunca alterar consenso para que pase una prueba.

### C. Proteger la decisión que firma el usuario (P0)
La firma Sigma sólo demuestra que la clave autorizó los bytes presentados: no confirma que la pantalla mostrase correctamente los destinatarios, contrato, activo o coste.

Antes de firmar, una cartera separada del indexador debe recalcular desde la transacción: contrato, génesis, IDs completos de tokens, inputs, outputs, cambio, scripts de destinatarios, valor bloqueado, min-out, gasto máximo y caducidad. Si difiere del intento aceptado, rechazar. Nada de excepciones administradas por un operador.

### D. Propiedades adicionales propuestas para contratos (P0/P1)
Probar como invariantes independientes, además de los tests ya existentes:
- **No confiscación:** ni una firma de administrador ni una sustitución de indexador deben permitir redirigir fondos de terceros.
- **No pérdida por cancelación:** todos los tokens bloqueados vuelven a la dirección indicada; pérdida nativa máxima declarada y acotada; caso extremo de valor mínimo y patrocinador insuficiente.
- **Conservación y tipado:** asset-ID exacto, cantidades no negativas y dentro de rangos, cero tokens imprevistos; operaciones aritméticas sin overflow/underflow.
- **Anti-replay de intención:** transacción concreta, origen de red y contrato fijados antes de firma. El hash del intento offline NO es una firma ni una garantía de consenso.
- **AMM (si se introduce):** NFT único del pool, actualización válida de reservas, preservación de proporcionalidad LP, límites de slippage, pruebas de primera provisión/donaciones, redondeos adversariales y cotas de coste.
- **Liveness bajo fallos:** reembolso/cancelación tras fallos de ejecutor o nodo, tasas adecuadas, interrupciones/reorganizaciones, con hipótesis y ventanas de tiempo expresas.

### E. Dependencias y evidencia de ejecución (P0)
- Mantener SHA completo y licencia por archivo de upstream, además de hash de artefactos construidos.
- Comparar los bytes de ErgoTree entre compilaciones, procesos, plataformas y versión del runtime; cualquier cambio requiere análisis de semántica.
- Conservar workflows con permisos mínimos y acciones fijadas a commit. El CI **no** reemplaza reglas de protección de ramas ni revisión humana (issue #6).
- Auditar dependencias y binarios sin asumir que herramientas antiguas con pruebas exitosas son seguras o mantenidas.
- Repetir verificación formal con toolchain mantenido o documentar explícitamente el bloqueo (issue #8).

## 3. Separar problemas para no introducir riesgo nuevo

1. **Core y minería:** auditoría separada. La seguridad de un DEX no protege una blockchain con hashrate insuficiente o validadores inconsistentes.
2. **DEX nativo:** solo activos de la misma cadena, sin puente en V1.
3. **Atomic swaps externos:** investigar después de probar contratos y liveness nativos; publicar modelo de amenazas específico (confirmaciones de ambas cadenas, reorg, ventanas de refund, fallos y diferencias de reloj).
4. **Pools de minería tipo Lithos:** proyecto independiente, con auditoría de NISPs, pruebas de fraude, vigilancia y reglas económicas propias; jamás incorporar emisión extra o modificar las 28M SYPC de diseño por copiar otro protocolo.

## 4. Puertas de salida objetivas (todas obligatorias)

| Puerta | Evidencia aceptable | Estado |
| --- | --- | --- |
| Proveniencia de referencia | commits/licencias/hashes de archivos importados | PARCIAL (ver `docs/UPSTREAM.md`) |
| Interpretación Sigma offline | scripts de laboratorio + test y logs reproducibles | PARCIAL (PR #9–#12; no SYPC) |
| Verificación formal restaurada | propiedades documentadas y verificador moderno | BLOQUEADA (#8) |
| Transacción SYPC íntegra | aceptación/rechazo de pruebas adversariales por validador real | NO REALIZADA (#13) |
| Cancelación recuperable | pruebas de coste, valor mínimo, sponsor ausente y reorg | NO REALIZADA (#13) |
| Carteras y UI de firma | decodificación independiente y rechazo de tx maliciosas | NO REALIZADA |
| Protección del repositorio | CI obligatorio y revisión humana en ramas protegidas | PENDIENTE (#6) |
| Auditoría externa | alcance, hallazgos, remediaciones y retest | NO REALIZADA |

**Decisión al cierre de esta revisión:** mantener todos los PR experimentales en borrador. Esta nota documenta prioridades, **no es una auditoría completada** ni mejora directa de la seguridad de fondos mientras los controles no estén implementados y probados en SYPC.
