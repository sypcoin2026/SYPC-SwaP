# Ensayo de ejecución SELL con intérprete Sigma 6.0.7

**Candidato P0 de laboratorio. NO desplegar. NO prueba SYPC Core.**

Este PR amplía el compilador nativo del PR #21 con una prueba de reducción y verificación ejecutada por la biblioteca **sigma-state 6.0.7**, no por el entorno histórico 4.0.5.

## Qué se pretende demostrar

El archivo `research/native6/src/main/scala/org/sypcoin/swap/NativeSigma607InterpreterSmoke.scala` construye un contexto sintético con:
- Una caja de venta `SELF` con 10 tokens de ID conocido y colateral nativo.
- Una segunda entrada de financiación del comprador. La cartera minera y las tesorerías existentes no intervienen.
- Un output de tokens y un cobro al propietario, con `R4 = SELF.id`, caja de cobro sin tokens y valor nativo por **encima del colateral más el precio**.
- Un intérprete `ErgoLikeInterpreter` real de Sigma 6.0.7, con configuración de test, que debe devolver **true** para la rama de ejecución válida sin firma del vendedor.

Casos negativos previstos: token incorrecto, cantidad de token inferior/superior, sin tokens, tokens extra, cobro insuficiente, destinatario de cobro erróneo, R4 incorrecto/ausente y cobro con tokens extra. Deben resultar **false**, no declararse exitosos por una excepción o por un simple mensaje del ejecutor.

## Cómo está aislado

- El contexto y los datos son objetos de memoria sintéticos. No hay red, wallets, scripts de minería, bases de datos ni REST.
- Los inputs de la fixture son objetos `ErgoBox`; la comprobación manual de importes/tokens no reemplaza validación de UTXO real.
- La prueba utiliza `UnsignedErgoLikeTransaction` para suministrar contexto. **No es una transacción completa firmada** y no acredita que una doble firma, el coste y las comisiones sean aceptables en SYPC Core.
- No se considera verificada la recuperación de los activos en condiciones reales de sponsor, renta, mínimos o congestión.
- La versión efectiva y activaciones del nodo SYPC siguen siendo desconocidas fuera de su entorno local. Este ensayo no puede autorizar un despliegue.

## Condición de aceptación

Se requiere CI en los dos Ubuntu con el intérprete Sigma 6.0.7 y una coincidencia de los resultados de 11 casos. Cualquier compilación fallida, excepción de un caso negativo, aceptación de un caso malicioso, divergencia de valores o error de las suites previas bloquea el PR. Los errores deben corregirse en el harness o los contratos **solo tras comprender la causa**, sin tocar el consenso.

Siguiente paso: validación nativa **del núcleo SYPC** exacto y de una transacción completa, en una cadena descartable, revisada por SYPC Swap Auditor. Mantener PR en borrador y no tocar testnet privada.
