# Evidencia de desarrollo: firma, devolución y UTXO de comisión

**Fecha:** 2026-11-12  
**Repositorio:** `sypcoin2026/SYPC-SwaP`, rama de investigación `work/sponsor-refund-guard-20261112`.  
**Alcance:** Scala, Sigma 4.0.5 y UTXOs exclusivamente sintéticas. Sin nodos SYPC ni fondos.

## Tabla de ejecución real

| Etapa | GitHub Actions | Entornos | Resultado |
| --- | --- | --- | --- |
| Firmas del contrato original | [43272988295](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43272988295) | Ubuntu 22.04 y 24.04 | 8/8 PASS cada uno |
| Protección exacta de devolución | [43273909351](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43273909351) | Ubuntu 22.04 y 24.04 | 17/17 PASS cada uno |
| Patrocinador opcional y rutas normales | [43275208073](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43275208073) | Ubuntu 22.04 y 24.04 | 27/27 PASS cada uno |
| Firma de **dos inputs** de la tx sintética | [43275928378](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43275928378) | Ubuntu 22.04 y 24.04 | 29/29 PASS cada uno |

Los errores intermedios se conservaron en el historial CI. Los valores PASS muestran el estado final del código de cada ejecución, no demuestran ausencia de vulnerabilidades.

## Qué se ensaya

- Contratos de compra y venta que conservan el cumplimiento sin custodio y añaden devolución protegida durante cancelación firmada.
- Rechazo por destinatario ajeno, token diferente o cantidad insuficiente, comisiones superiores al tope, UTXO extra con tokens, script del patrocinador no autorizado, inputs duplicados y tercera entrada.
- Firma de la entrada de orden y la del patrocinador con el mismo mensaje de transacción serializada, usando claves públicas de laboratorio derivadas de secretos públicos desechables.
- Invalidación de la prueba al cambiar bytes del mensaje una vez firmado; firmas ajenas rechazadas.
- En modelo de prueba: suma de entradas nativas igual a suma de salidas y dos identificadores UTXO distintos.

## Limitaciones

- El `ErgoLikeInterpreter` comprueba scripts individuales en un contexto sintético. **No** ejecuta la validación del nodo real de SYPC ni comprueba el conjunto UTXO de la red, mempool, doble gasto, dust, versiones de consenso, minado ni confirmaciones.
- El contrato de comisión se fija a un script **ficticio** de ensayo; `FeePropBytes` y `MaxCancelFee` no están aprobados para mainnet.
- La verificación formal histórica de Ergo con Stainless sigue bloqueada por dependencias discontinuadas. Portar las propiedades y re-demostrarlas continúa pendiente.
- No existe DEX ni wallet de intercambio desplegada, no hay liquidez y **no se autorizan depósitos reales**.

## Próximo criterio para declarar compatibilidad SYPC

Reproducir el test con el **binario de consenso SYPC** y sus parámetros reales, transacciones firmadas por cada input, validación de conservación global, coste, anti-replay y comprobaciones de dos nodos independientes. No cambiar consenso para conseguir que el test pase.
