# ADR-0003 — Orden SELL vinculada a activos y valor nativo (investigación)

**Fecha:** 12/11/2026  
**Estado:** candidata experimental. **NO APROBADA / NO DESPLEGAR**.  
**Base:** `AtomicSellSponsorRefund.sc`, sin alterar scripts legados, nodo ni consenso.  
**Motivo:** defensa por contrato de los términos concretos anunciados por el vendedor.

## Hallazgo

La rama `validFill` anterior solo exigía al comprador acreditar un output con `R4=SELF.id`, destinatario igual a `SellerPk` y `value >= MinNativeAmount`.

No garantizaba:
- Que la caja de orden contuviera **exactamente un token del identificador anunciado**, ni la cantidad acordada.
- Que el vendedor recuperara el valor nativo `SELF.value` bloqueado en su orden, **además del precio**.
- Que el output de cobro del vendedor no incluyera activos inesperados.

Esto no prueba robo a usuarios: la cartera podría controlar estas condiciones, pero la rama sin firma del vendedor deja esas reglas **fuera del consenso del contrato**. La mejora disminuye la dependencia de una interfaz correcta.

## Modificación experimental

La nueva rama `validFill` impone simultáneamente:
- `MinNativeAmount > 0` y `SellTokenAmount > 0`, parámetros vinculados al árbol del contrato.
- `SELF.tokens.size == 1`; `SELF.tokens(0)` debe ser exactamente `(SellTokenId, SellTokenAmount)`.
- Cobro en `OUTPUTS(1)` con `R4 == SELF.id`, `propositionBytes == SellerPk.propBytes` y **sin tokens**.
- `OUTPUTS(1).value >= SELF.value + MinNativeAmount` usando `BigInt` para evitar overflow de sumas intermedias.

La cancelación conserva la rama ya probada `SellerPk && safeCancel`, con devolución íntegra de tokens y saldo nativo y patrocinio opcional. Una caja mal constituida podrá cancelarse mediante firma legítima si satisface los requisitos de salida y comisión; **su ejecución de venta queda bloqueada**.

## Pruebas de regresión

`SponsorRefundCompileSpec.scala` verifica que el `ErgoTree` cambia si alteramos token ID, cantidad o precio nativo.

`SponsorRefundSignatureSpec.scala` ejecuta con `ErgoLikeInterpreter` de Sigma 4.0.5:
- Venta correcta sin firma del vendedor.
- Rechazo por token equivocado, cantidad mayor/menor, sin tokens y activos extra.
- Rechazo de pago inferior al precio **más** el nativo de `SELF`.
- Rechazo de tokens inesperados en el cobro del vendedor.
- Repetición de pruebas de cancelación y patrocinio.

## Amenazas / requisitos pendientes

1. Las transacciones de laboratorio pueden ser sintéticas e incompletas; las pruebas de script **no** acreditan conservación global, inputs del comprador firmados, aceptación P2P ni stateRoot en nodo SYPC.
2. No hay política real validada de valor mínimo por caja, renta, fee y coste de ejecución; el nuevo requisito de pago debe comprobarse en **transacciones completas** antes de integrar.
3. Un propietario puede fijar un precio inadecuado al crear la orden; se requiere una cartera capaz de mostrar condiciones y rechazar cambios engañosos.
4. El hash del contrato cambia; nunca reemplazar en silencio un script desplegado ni atribuir las propiedades nuevas a órdenes antiguas.
5. No está restablecida la verificación formal actualizada (issue #8); liveness y recuperación aún bloqueados (issue #13).

**Conclusión provisional:** la venta únicamente debe ejecutarse cuando se cumplen los activos y el valor exactos que el vendedor fijó. Sin auditoría independiente, esta propuesta sigue siendo un experimento y no puede manejar dinero real.
