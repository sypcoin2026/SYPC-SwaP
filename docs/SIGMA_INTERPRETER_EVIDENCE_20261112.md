# Evidencia experimental — intérprete Sigma y reproducibilidad

Fecha: 2026-11-12

## Resultado real

- [GitHub Actions — run 43260997269](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43260997269): 11 pruebas con `ErgoLikeInterpreter` de Sigma 4.0.5: **11 PASS, 0 FAIL**.
- [GitHub Actions — run 43261466638](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43261466638): 12 pruebas (incluido un control de fingerprint) **PASS en Ubuntu 22.04 y Ubuntu 24.04**, Java 11.
- Ambos entornos generaron exactamente las mismas huellas SHA-256 del ErgoTree compilado para cada conjunto de parámetros sintéticos:

| Contrato candidato | SHA-256 del ErgoTree |
| --- | --- |
| `AtomicBuy.sc` | `096c67a754bb9ba048cb06d8dc3cbb61ada913dacfe34fbb6d18a83401bde0bb` |
| `AtomicSell.sc` | `9f1a281445976e701d7c23a50f77299856a06b319cffbafdd98eeee86acdceb6` |

Los hashes se calculan sobre los **bytes serializados** del ErgoTree, no sobre el texto del archivo Scala. El test ahora exige esas huellas de forma explícita; un cambio de bytes obliga a revisar la línea base antes de aceptarlo.

## Qué se comprobó realmente

- Interpretación de un contrato de **compra** con output correcto.
- Rechazo de token equivocado, cantidad inferior a la mínima, destinatario ajeno, R4 ausente o falso y orden incorrecto de outputs.
- Interpretación de un contrato de **venta** con pago correcto.
- Rechazo de pago insuficiente, destinatario ajeno, R4 ausente o falso y outputs incorrectos.
- Repetición de compilación y huellas en entornos Linux independientes, usando entradas de laboratorio fijas.
- Todo se hizo sin claves privadas, fondos, servidores REST, red SYPC ni minería.

## Herramientas y procedencia

- `spectrum-finance/ergo-dex` commit `8fe94e1f8b4e1ab9402fca6fbc3955e3ad1415f7`, con `SigmaPlatform.scala` blob `a4b079008592098509cc03bd931a9ef4b5f14518`.
- Scala 2.12.15, Sigma-State 4.0.5, Java 11. Actions GitHub fijadas a commits completos; `contents: read`.
- Pruebas en `research/scala/AtomicSigmaInterpreterSpec.scala`. Scripts candidatos en `research/ergo_script/`, adaptados de los originales de Ergo Contracts (CC0).

## Límites de seguridad obligatorios

1. **No prueba consenso SYPC**: se ha utilizado el intérprete de la versión Sigma del laboratorio, NO el binario del nodo SYPC.
2. **No prueba validez global de transacciones**: las cajas UTXO son sintéticas. No se valida la conservación de fondos entre inputs/outputs, comisiones, tokens realmente emitidos, costes impuestos por un nodo, mempool ni doble gasto.
3. **No prueba firma de cancelación**: sólo se ensayan rutas de cumplimiento con prueba de conocimiento vacía; el circuito del propietario todavía necesita test criptográfico independiente.
4. **No demuestra equivalencia con verificación formal**: Stainless heredado sigue bloqueado por dependencia obsoleta y hay que re-demostrar propiedades.
5. **No hay despliegue, DEX operativo ni fondos reales**. Los hashes de un contrato de investigación no son direcciones de contrato autorizadas para usuarios.

## Próximo gate

Para acercarnos a la mainnet tendremos que repetir los escenarios sobre el intérprete del núcleo SYPC y demostrar las reglas completas con un nodo independiente, sin cambios de consenso. El test harness actual es una herramienta de desarrollo que debe seguir separado del software distribuido.

