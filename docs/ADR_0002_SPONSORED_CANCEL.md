# ADR-0002 — Cancelación con UTXO adicional del propietario

Fecha: 2026-11-12  
Estado: **INVESTIGACIÓN / NO DESPLEGAR**. No aprobado para SYPC.

## Motivación

La primera protección contractual de cancelación (ADR-0001) impide desviaciones bajo una firma del propietario, pero restringe el gasto a una sola caja UTXO. Si la caja contiene tokens pero poco valor nativo, puede quedar **imposible** pagar comisión y construir una devolución que satisfaga el mínimo de valor de una salida válida. Es un problema de recuperabilidad y no debe aceptarse.

## Variante experimental

Los nuevos scripts `AtomicBuySponsorRefund.sc` y `AtomicSellSponsorRefund.sc` admiten exactamente una de estas estructuras de cancelación:

**Modo A — La orden financia su propia comisión:** la transacción gasta únicamente SELF y devuelve al propietario el saldo, descontando una comisión positiva dentro del máximo.

**Modo B — El propietario aporta otra UTXO:** exactamente dos inputs, SELF como primera entrada y una segunda caja UTXO **nativa, sin tokens y bajo el mismo script P2PK del propietario**. Exige que la suma de la devolución y comisión sea exactamente la suma del valor nativo bloqueado más el valor del patrocinador. La devolución del propietario debe contener **al menos todo el valor nativo de SELF**, más el cambio del patrocinador que reste después de la comisión.

En ambos modos el propietario debe **firmar** el gasto de la orden; los tokens bloqueados deben conservarse en la salida de devolución sin modificación; sólo se permite una salida de comisión sin tokens al script declarado por los parámetros del contrato, y no hay salidas adicionales.

Un operador externo o indexador no debe poder elegir arbitrariamente el script del patrocinador. Esta variante usa **la propia cartera del dueño**. No crea nuevas monedas ni cambia consenso.

## Garantías propuestas del contrato

- `INPUTS.size` es 1 o 2, `INPUTS(0).id == SELF.id`.
- Si hay `INPUTS(1)`, debe ser distinta de SELF, tener `tokens.size == 0` y `propositionBytes == OwnerPk.propBytes`.
- Exactamente dos salidas; la primera al propietario y con `tokens == SELF.tokens`, la segunda al script de comisión fijado.
- Valor de la comisión positivo y acotado por `MaxCancelFee`.
- Conservación de valor nativo con operaciones `toBigInt` intermedias.
- En modo patrocinado, la devolución es mayor o igual al valor nativo original de SELF.
- Firma del propietario requerida en la rama de cancelación; se conserva la rama original de cumplimiento de la orden para ejecución sin custodia.

## Limitaciones de extrema importancia

**L1 — Esta prueba no firma el patrocinador.** `ErgoLikeInterpreter.verify` evalúa el script de la orden de forma individual. Que el contexto contenga dos entradas NO demuestra que la transacción completa satisfaga la prueba de gasto de la segunda entrada. El nodo real debe verificar **ambos** scripts y las reglas globales.

**L2 — Sin UTXO nativa libre, la cancelación puede seguir bloqueada.** El diseño mejora la recuperabilidad cuando el propietario tiene otra caja con fondos para comisión; no garantiza que siempre la tenga ni que la orden sea válida con un valor nativo demasiado bajo. Una política de reservas y preflight de la cartera sigue siendo imprescindible.

**L3 — No se han probado costes y límites del consenso SYPC**, min box value, renta de almacenamiento, versiones de ErgoTree, reorgs, maduración, ni liveness con nodos.

**L4 — `FeePropBytes` debe verificarse contra la cadena SYPC** y la comisión real, no contra una fuente no confiable.

**L5 — Los contratos originales de Ergo siguen sin verificación formal reproducida en toolchain moderno**. El port y sus propiedades deberán demostrarse de nuevo.

**L6 — Pueden existir restricciones de coste/atomicidad o incompatibilidades cuando dos inputs requieren firma**. No deben cambiarse reglas de consenso para sortear un fallo de prueba.

## Plan de pruebas (laboratorio)

- `research/scala/SponsorRefundCompileSpec.scala`: compilación, reproducibilidad y constantes fijadas.
- `research/scala/SponsorRefundSignatureSpec.scala`: firmas Sigma de prueba, aceptación de cancelación y rechazos por scripts ajenos, tokens adicionales, importe insuficiente, exceso de fee, tercera entrada y SELF duplicado.
- `.github/workflows/sponsor-refund-lab.yml`: pruebas en dos Ubuntu aislados, Java 11, Spectrum/Sigma 4.0.5 fijado a commit.
- En todas las pruebas: únicamente datos sintéticos; sin transacciones reales ni fondos.

**Decisión vigente:** mantenerlo como experimento, exigir validación nativa SYPC y auditoría externa, y NO adoptar como contrato de producción hasta demostrar también las reglas de recuperación.
