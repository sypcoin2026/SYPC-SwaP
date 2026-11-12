# ADR-0001 — Cancelación protegida en el contrato (investigación)

Fecha: 2026-11-12  
Estado: **PROPUESTA NO ADOPTADA** — laboratorio Sigma 4.0.5; sin validación SYPC ni autorización para fondos reales.

## Problema comprobado

Los contratos originales de intercambio atómico de Ergo (`AssetsAtomicExchange.scala`, commit `17ed58b39460e5520de56f615936d918603a3b9e`, CC0-1.0) permiten gastar una orden mediante:

1. Cumplimiento verificable de condiciones de intercambio, **o bien**
2. Prueba criptográfica de la clave del propietario.

La segunda rama **no impone requisitos de devolución** a los outputs. Una firma válida no puede falsificarse por ello, pero el usuario podría firmar una transacción engañosa creada por una interfaz comprometida. La mitigación en la cartera es necesaria, pero además queremos estudiar una protección contractual.

## Candidato de investigación

Los scripts experimentales `research/ergo_script/AtomicBuyRefundGuard.sc` y `AtomicSellRefundGuard.sc` conservan la rama de cumplimiento y sustituyen la rama de cancelación por:

```text
(cumplimiento original)
    OR
(firma del propietario Y condiciones exactas de devolución)
```

Condiciones para la **rama de cancelación** en esta prueba:

- Sólo **una entrada** (SELF); evita mezclar otros fondos en el escenario reducido.
- Exactamente **dos salidas**: `OUTPUTS(0)` al script del dueño, `OUTPUTS(1)` al script fijo de comisión.
- Los tokens de la primera salida son **idénticos** a los tokens bloqueados; la segunda salida carece de tokens.
- `native_refund + native_fee == SELF.value`, con operaciones intermedias de precisión ampliada.
- El importe de comisión es positivo y no puede superar `MaxCancelFee`.
- El propietario debe seguir presentar una **prueba Sigma real**; una salida correcta no equivale a consentimiento.

Las constantes `FeePropBytes` y `MaxCancelFee` quedan fijadas en el ErgoTree; la app no puede modificarlas silenciosamente para una orden ya creada.

## Ventajas previstas

- Desviar un reembolso durante una cancelación **firmada** debería ser rechazado por el script, no sólo por la wallet.
- Doble defensa: firma del propietario + devolución exacta.
- Los ejecutores de mercado no obtienen claves ni permisos administrativos.
- El contrato puede verificarse contra escenarios adversariales de forma independiente.

## BLOQUEOS de seguridad y disponibilidad

**BG-01 — Riesgo grave de fondos bloqueados:** exigir una sola entrada puede impedir cancelar cuando el valor nativo de SELF no alcanza simultáneamente la comisión y el mínimo exigido para la caja de retorno. Si esta condición no puede cumplirse, aunque el propietario tenga más dinero en otras cajas, **el contrato puede bloquearle sus activos**. No desplegar hasta diseñar y probar una ruta de recuperación financiada externamente, o establecer restricciones y reservas demostrablemente suficientes en cada orden.

**BG-02 — Política de comisiones:** la prueba utiliza un script de comisión sintético. Antes de cualquier despliegue necesitamos identificar y vincular el script correcto de minería del núcleo SYPC y probar sus reglas.

**BG-03 — Costes y versiones de ErgoScript:** Sigma 4.0.5 no equivale al intérprete final de SYPC. Debemos medir coste de scripts, compatibilidad de cabeceras y cumplimiento de límites de red.

**BG-04 — Estado global:** la reducción de un script NO demuestra conservación global entre todas las entradas y salidas, mempool, confirmaciones ni doble gasto. Hace falta prueba de la transacción completa en dos nodos SYPC independientes.

**BG-05 — Auditoría formal:** la verificación original con Stainless 0.6.1 permanece bloqueada por dependencias obsoletas. La nueva rama contractual necesita una nueva demostración de invariantes, no heredada.

**BG-06 — Recuperabilidad y permisos:** falta estudiar expiración, cancelación frente a desconexión, clases de activos, tokens ordenados/canónicos y costes de Dust/Storage Rent, así como ausencia de claves administradoras.

**BG-07 — Riesgo de fee script:** `FeePropBytes` es una constante externa que debe derivarse de parámetros de red verificados, no de una API o interfaz controlada por terceros.

## Matriz de pruebas

- `research/scala/RefundGuardCompileSpec.scala`: compilación y enlace de parámetros (laboratorio).
- `research/scala/RefundGuardedSignatureSpec.scala`: firma Sigma real con claves **sintéticas desechables**; escenarios legítimos y maliciosos.
- CI workflow de laboratorio histórico (conservado en el historial Git); en la rama auditada actual los mismos casos están incluidos en `.github/workflows/security-sigma-current.yml`: dos runners Linux con toolchain, versiones y commits fijados.
- **No** se ejecuta ningún nodo SYPC, no se opera con claves reales y no se generan operaciones en la blockchain.
- Los resultados y los fallos deben conservarse en esta ADR cuando se verifiquen en GitHub Actions.

## Decisión propuesta

**No adoptar aún el contrato de cancelación con entrada única.** Investigar primero un diseño que no sacrifique la recuperabilidad de los fondos y mantenga la verificación exacta de outputs. Requerimos pruebas de éxito, rechazo adversarial, coste, liveness y revisión independiente antes de elegir implementación final.

La prioridad de SYPCoin no es sólo impedir un robo: es impedir también que una protección excesivamente restrictiva bloquee permanentemente los ahorros de los usuarios.
