# Pruebas Sigma 6.0.7: BUY y SELL con comprobación independiente

**Fecha:** 14/11/2026 · **Estado:** laboratorio sintético, sin nodo SYPC, wallets ni testnet.

Esta rama extiende la verificación nativa Sigma 6.0.7 con **BUY**, sin duplicar el constructor de contexto ni el compilador de `NativeSigma607InterpreterSmoke.scala`. Ambos reutilizan el mismo `ErgoLikeInterpreter` y `NativeSigma607Compile`.

## Matriz de pruebas

| Lado | Casos válidos | Casos deliberadamente inválidos | Resultado exigido |
| --- | ---: | ---: | --- |
| SELL | 1 | 10 | True para fill válido; False para los 10 ataques |
| BUY | 1 | 7 | True para fill válido; False para los 7 ataques |

BUY verifica el primer output de tokens que pertenece a `BuyerPk`, contiene el token `TokenId` con al menos `MinTokenAmount` y registra `R4 = SELF.id`. Rechaza token equivocado, cantidad insuficiente, ausencia de tokens, destinatario ajeno, referencia errónea, referencia ausente y orden de outputs intercambiado.

SELL conserva las condiciones ya acreditadas de token/cantidad exactos en SELF, cobro del precio más colateral nativo, identidad de vendedor y R4.

## Revisor independiente

`tools/review_native6_compilation.py` comparte el mismo motor de análisis para BUY y SELL, pero maneja **listas cerradas y distintas** de escenarios y comprueba:
- Una prueba válida por cada lado.
- Diez rechazos SELL y siete BUY, sin duplicados.
- Coincidencia de seis huellas de ErgoTree con `research/native6/fingerprints.json`.
- Rechazo de casos inventados, faltantes, logs con error, marcadores manipulados o duplicados.
- Nunca declarar `native_consensus_proven` ni autorizar despliegues o fondos.

## Límites

Son transacciones sintéticas NO firmadas, con balances manualmente comprobados para los casos positivos. La comprobación del intérprete no prueba conservación nativa global, min-box, fees, firma del input contrapartida, validación de SYPC Core, liveness de sponsor, reorg ni una blockchain real. La prueba no debe interpretarse como autorización para lanzar el DEX.

**Próximo gate:** réplica de estos resultados en un test nativo del mismo commit que la testnet SYPC y transacciones completas con firmas y costes, en red descartable; sin cambiar consenso.
