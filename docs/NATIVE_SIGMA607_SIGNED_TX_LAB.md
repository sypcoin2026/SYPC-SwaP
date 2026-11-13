# SYPC Swap — transacción SELL firmada en memoria con Sigma 6.0.7

**Estado:** P0 LAB / SIN FONDOS / NO DESPLEGAR / NO VALIDADO EN SYPC CORE.  
**Base:** PR #23, `audit/native-sigma607-buy-regressions-20261114` @ `26624d3a382de0d2ef3ef0b6a83f109a2cf50d5e`.  
**Código:** `research/native6/src/main/scala/org/sypcoin/swap/NativeSigma607SignedTx.scala`.

## Qué estamos probando realmente

1. Una caja SELL sintética bloquea exactamente 10 unidades de token de prueba con 2 000 000 unidades nativas; otra caja del comprador aporta 1 001 200.
2. Se crea una `UnsignedErgoLikeTransaction` completa *como objeto de biblioteca* con tres outputs: pago de 10 tokens y 1 000 000 nativos al comprador; 2 001 000 al vendedor (con `R4 == SELF.id`); 200 al output de comisión sintético.
3. Las sumas de entrada y salida nativa se verifican con `BigInt` y se comparan mapas exactos de tokens por identificador. Rechazamos referencias a inputs repetidos.
4. Se genera una prueba Sigma para **cada input contra exactamente el mismo `messageToSign`**. La orden SELL permite la ejecución sin firma del vendedor si se cumplen las restricciones del contrato (**prueba vacía intencionada**); el input del comprador sí exige la prueba criptográfica correspondiente a su clave pública.
5. Se serializa la transacción firmada, se deserializa, se contrasta mensaje y bytes del proof y se verifican **ambos inputs de forma independiente** con `ErgoLikeInterpreter` de Sigma 6.0.7.
6. Rechazos adversariales: prueba del comprador ausente, prueba forjada por otra identidad, pago modificado después de firmar, `R4` incorrecto, destinatario del token modificado después de firmar e input duplicado. Los cinco primeros se someten a la verificación de scripts/firmas; el último se rechaza mediante guard explícito de estructura, **NO como prueba de rechazo de consenso**.

Todas las claves privadas empleadas en esta fixture son enteros **públicos y conocidos**, nunca credenciales personales. Ninguna cuenta de la testnet está conectada.

## Lo que NO demuestra

- No se ha ejecutado el validador de **sypcoin-core** ni se ha comprobado el runtime de nuestro nodo actual, activación de ErgoTree, UTXO autentificados, límites de coste, min-box, rent, fee de protocolo o admisión en mempool.
- Los importes son solo valores sintéticos para probar aritmética, pruebas y serialización. No se ha creado un bloque, ni una moneda, ni una transferencia real.
- La recuperación de órdenes con patrocinador y la firma de **dos entradas que ambas exijan firmas** son un **siguiente ensayo**; una venta sin firma del vendedor no sustituye esa prueba.
- Un log con PASS tampoco constituye evidencia autenticada por nodo. El Auditor debe comprobar la estructura de transacciones y versiones nativas, no confiar solo en las etiquetas escritas por el productor.

## Condiciones para avanzar después

1. El ensayo de transacción firmada pasa de forma reproducible en Ubuntu 22.04 y 24.04 con `sigma-state 6.0.7`.
2. SYPC Swap Auditor rechaza evidencias contradictorias, ausentes y duplicadas del ensayo, sin autorizar dinero ni despliegue.
3. Se realiza una prueba equivalente de cancelación **con dos firmas reales** y patrocinio; reembolso íntegro, fees y mínimos por caja.
4. Se ejecutan pruebas nativas en `sypcoin-core` con el commit y runtime exactos de la testnet, en laboratorio descartable y con revisión independiente.
5. Solo tras aprobar todo lo anterior se puede considerar una prueba restringida en la testnet privada que ya está funcionando.

**Prohibido:** modificar consenso para obtener PASS, reutilizar claves públicas de la fixture para dinero, tocar nodos y wallets reales o desplegar contratos sin autorización explícita.
