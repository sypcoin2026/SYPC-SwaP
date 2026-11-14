# SYPC Swap — cancelación SELL patrocinada con dos pruebas Sigma 6.0.7

**Estado: SOLO LABORATORIO / NO DESPLEGADO / NO APTO PARA FONDOS.**  
**Dependencia:** PR #24 `audit/native-sigma607-signed-tx-20261114`; solo pruebas de biblioteca Sigma 6.0.7.

## Propósito

La ejecución SELL normal puede gastar el contrato sin la firma del vendedor porque las condiciones del intercambio están codificadas en su ErgoTree. **La cancelación es distinta:** el vendedor debe firmar la devolución y, si aporta una caja de patrocinio para la comisión, también debe demostrar que puede gastar esa segunda caja.

A diferencia de una firma para un solo input, esta prueba crea dos `ProverResult` Schnorr **no vacíos**, uno por cada caja, sobre un único `messageToSign`, serializa la transacción, la deserializa y verifica ambas entradas por separado con `ErgoLikeInterpreter` Sigma 6.0.7.

## Fixture exacta, solo datos ficticios

- **Orden SELL:** 2 000 000 unidades nativas, 10 tokens del ID de prueba; bloqueada bajo el contrato de cancelación segura.
- **Patrocinador:** 1 000 unidades nativas, sin tokens, bloqueadas por la misma identidad del vendedor.
- **Reembolso:** 2 000 800 unidades nativas + los 10 tokens íntegros al vendedor.
- **Comisión sintética:** 200 unidades nativas, con un script de cobro fijado en el contrato.
- **Conservación:** entradas = salidas en nativo y tokens; firma de cada input contra el **mismo hash de transacción**.

Las claves del laboratorio son escalares públicos y predeterminados. No usarlos para ninguna wallet personal ni tesorería SYPC.

## Regresiones adversariales (8)

1. Falta prueba de firma de la orden.
2. Falta prueba de firma del patrocinador.
3. Prueba del patrocinador realizada por una identidad ajena.
4. Reembolso redirigido después de firmar.
5. Comisión por encima de la cota fijada en el contrato.
6. Patrocinador con menos nativo que la comisión, que obligaría a reducir el colateral de la orden.
7. Patrocinador con tokens, aunque el contrato exige patrocinio exclusivamente nativo.
8. Output de comisión con script distinto al fijado.

Los cuatro primeros se comprueban contra las pruebas/firmas de la transacción ya firmada; los cuatro últimos **no deberían poder generar la prueba de cancelación del propietario**, y deben rechazarse sin excepciones convertidas en PASS.

## Qué falta demostrar

**NO equivale a prueba de liveness.** Las cajas sintéticas permiten valores inferiores a los mínimos nativos operativos, no aplican rent, min-box ni restricciones de coste/fee del validador SYPC. Una cancelación puede ser criptográficamente correcta y aun así no ser económicamente ejecutable. No se prueba el mempool, sincronización, doble gasto, reorganizaciones ni que las recompensas de la testnet existente permitan patrocinar estas transacciones.

El siguiente paso será una prueba de admisión completa con **sypcoin-core del commit y entorno exactos**, sobre una cadena desechable y sin exponer la red doméstica. El Auditor deberá revisar firma de dos inputs, conservación nativa/tokens, scripts, costes, estado antes/después y recuperabilidad antes de cualquier GO.

**Ninguna modificación de consenso, ningún cambio de contratos desplegados, ninguna operación con fondos reales.**
