# SYPC Swap — Revisión de seguridad del intercambio atómico

Fecha: 12 de noviembre de 2026. Nivel de prueba: **investigación de código, modelo matemático, compilación ErgoScript con Sigma 4.0.5**. Sin firma, transacciones reales ni despliegue en SYPC.

## Fuentes fijadas

- Ergo Contracts `17ed58b39460e5520de56f615936d918603a3b9e`, `verified-contracts/.../AssetsAtomicExchange.scala`; blob `03214d52d9e519843f75abe0cc6e46f33dd99d23`.
- Spectrum ErgoDEX `8fe94e1f8b4e1ab9402fca6fbc3955e3ad1415f7`, usado sólo como banco de pruebas Sigma 4.0.5 (Scala 2.12.15).
- Los dos scripts candidatos (comprar/vender) en `research/ergo_script/` **no se han desplegado**. Licencia de origen CC0.

## Lógica concreta del contrato original

**Compra:** el propietario puede cancelar mediante su firma, o terceros pueden completar la orden sólo si `OUTPUTS(0)` contiene el token y cantidad requerida, va dirigido a la proposición del comprador y registra `SELF.id` en R4.

**Venta:** análogamente, el propietario puede cancelar mediante su firma; terceros sólo gastan la orden si `OUTPUTS(1)` paga el importe nativo requerido al vendedor y registra `SELF.id` en R4.

Estas condiciones son **locales al input cuyo contrato se ejecuta**. No sustituyen reglas globales del nodo sobre conservación de activos, firmas, comisiones, costes de script y aceptación de toda la transacción.

## Hallazgos de diseño y mitigaciones

| ID | Riesgo concreto | Estado | Mitigación exigida |
| --- | --- | --- | --- |
| AT-01 | La rama de firma del propietario permite gastar sin validar los outputs de devolución | **Abierto — P0 para wallet/fondos reales** | La cartera debe comparar toda la transacción con la intención; explorar reforzar la devolución también en el script |
| AT-02 | La venta no fija token ID en su predicado: depende de los activos que de verdad contiene la caja bloqueada | **Abierto — P0** | La wallet verifica UTXO real, tokens, amounts y script, no un registro de mercado |
| AT-03 | Las posiciones de los outputs son fijas (0 compra, 1 venta) | **Controlado sólo en modelo offline** | Constructor de tx y firmante deben validar índices y outputs de la transacción completa |
| AT-04 | Un usuario puede firmar una cancelación que usa inputs ajenos o que redirige fondos si el frontend es malicioso | **Controlado sólo en modelo offline** | `preflight_single_input_cancel`: exige una única entrada de orden y destinos autorizados, devuelve activos exactos |
| AT-05 | Token ID repetido o suplantado puede falsear balances si el software sólo suma cantidades | **Rechazado por el preflight offline** | IDs completos, sin duplicados en cada output y conservación exacta; validar en nodo |
| AT-06 | Contrato compilado con bytes diferentes al reutilizar estado de SigmaPlatform | **Mitigado en laboratorio, no cerrado globalmente** | Compilador aislado, tests de bytes, pinning de bytecode y prueba de repetibilidad entre entornos |
| AT-07 | Diferencias entre Python/Sigma/consenso SYPC | **Abierto — P0** | Repetir casos en compilador, intérprete SYPC real y dos nodos validadores |
| AT-08 | Integridad o dependencia antigua de compilación/formal | **Abierto — P0** | Ver `ERGO_STAINLESS_MIGRATION.md`; no desactivar prueba formal silenciosamente |

### Restricciones del modelo estricto de cancelación

El prototipo `sypc_swap/cancel_preflight.py` **no firma ni ejecuta transacciones**. Exige:

- Una sola entrada, identificada exactamente por ID de caja de la orden.
- Salidas únicamente al propietario y una salida de comisión a un script confiable, diferente al propietario.
- Todos los tokens de la caja devueltos exactamente a la proposición del dueño, sin tokens desconocidos o repetidos en una misma caja.
- Valor nativo exacto: `fondos_al_propietario + comision = valor_bloqueado`.
- Una comisión positiva, única y por debajo de la cota local, sin tokens ni registros inesperados.
- Rechazo de cero, desbordamiento de 64 bits, colecciones mutables donde está prohibido y destinos ajenos.

**Advertencia:** los IDs de caja, scripts y balances son datos que en esta prueba se pasan a mano. Una wallet real debe **autenticarlos contra un nodo SYPC validado**, comprobar la tx serializada entera y exigir la aprobación consciente del usuario. Ni el hash de la intención ni la prevalidación offline son pruebas criptográficas.

## Evidencia verificable

- [Laboratorio Scala: 4/4 tests candidatos PASS](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43239483382). Incluye cinco compilaciones adicionales de cada candidato con contextos independientes en una misma ejecución.
- [Laboratorio Python: 134/134 PASS en 3.12 y 3.13](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43240291935). Tests del modelo original, propuestas de trade, AMM, devolución/cancelación estricta, manifiestos de origen y tripwire AST.
- [Referencias originales de Spectrum: 2 tests PASS](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43237243130). No equivale a toda su suite ni a auditoría.
- `tests/test_atomic_reference.py`, `tests/test_cancel_preflight.py`, `tests/test_trade_preflight.py` contienen entradas adversariales reproducibles.

## Decisiones abiertas que NO debemos forzar

1. ¿Exigir devolución también en el contrato de cancelación? **Propuesta: sí, si podemos formalizar y demostrar la seguridad del cambio**, preservando una ruta fiable de recuperación y un coste razonable.
2. ¿Cómo se representan los pagos y el cambio de comisión en la cadena SYPC? Requiere observar reglas reales de un nodo, no adivinar.
3. ¿Qué versión y parámetros de ErgoTree/ErgoScript son admitidos por la cadena SYPC final? Hasta comprobarlo, no existe port validado.

**Regla de promoción:** `tests Python` ≠ `ErgoTree compila` ≠ `script ejecutado en testnet SYPC` ≠ `fondos seguros`. No fusionar cambios monetarios sin revisión y auditoría externa.

