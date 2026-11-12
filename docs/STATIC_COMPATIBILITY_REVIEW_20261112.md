# Revisión estática de compatibilidad y fuentes (12/11/2026)

**Tipo de evidencia:** lectura estática de archivos de GitHub fijados a commits. **No** se ha compilado ni ejecutado contrato Ergo/SYPC. No se ha usado nodo, cartera, minería ni saldo.

## Evidencia del núcleo SYPC

Repositorio privado `sypcoin2026/sypcoin-core`, rama `work/linux-node-lan-20261111`, commit `72a6a9a3c8add39c7f0bb978819b013cc4a0404b`.

Archivo: `ergo-core/src/main/scala/org/ergoplatform/modifiers/mempool/ErgoTransaction.scala`, blob Git `00a77981245a1f1035f5958bfe2e95a4fe04c9f0`.

La inspección confirma **presencia del código**, no ejecución:

- `validateStateless`: validación estructural de transacciones.
- `verifyInput`: invocación de `ErgoInterpreter.verify` para comprobar los scripts de cada input.
- `verifyAssets`: comprobación de conservación de activos, con excepción de acuñación para ID derivado del primer input. **No** significa acuñación de nuevas SYPC nativas.
- `outputCandidates`, `boxesToSpend` y `dataInputs` conservan la estructura eUTXO que requieren los DEX heredados.

**Pendiente:** demostrar que el binario real aplica exactamente esa ruta, que las reglas de versiones permiten el script concreto y que los prefijos/identidades de red son correctos. El antecedente de discrepancia entre prefijos de direcciones SYP/Ergo exige rechazar direcciones externas por defecto.

## Contratos originales conservados

Los ocho archivos elegidos de Ergo y Spectrum se conservan en `third_party/`, con licencias CC0 y hashes de blobs verificados en GitHub tras su publicación. Consultar `third_party/REFERENCES.json`.

### Modelo atomic exchange (Ergo)

`AssetsAtomicExchange.scala` tiene dos vías: firma del propietario para cancelar o condiciones de output referenciado mediante `SELF.id` para completar compra/venta. El repositorio de Ergo incluye propiedades formales específicas para estas condiciones. **No** implica que las propiedades estén verificadas para un contrato adaptado a SYPC.

`DexLimitOrder.scala` contiene un modelo mucho más complejo de órdenes parciales, spreads y tasas; **no debe ser primera opción de port**. Revisar especialmente multiplicaciones y acumulación `Long`, casos extremos, ordenación de inputs y pruebas de cancelación. Sin emitir juicio de vulnerabilidad hasta demostrarla.

### Modelo AMM (Spectrum)

`contracts/amm/cfmm/v1/n2t/Pool.sc` comprueba continuidad de script, NFT de pool, tokens y fee, y transición de swap con `FeeDenom = 1000`, además de lógica de depósitos/retiradas.

`contracts/amm/cfmm/v1/t2t/Pool.sc` protege el par token-token y requisitos de reservas/LP. El uso de constantes externas exige conocer el procedimiento de compilación; **no es desplegable como archivo aislado**.

Los `SwapBuy.sc` y `SwapSell.sc` de v3 dependen de identificadores del pool, constantes, propbytes, precios mínimos, ejecutores y fees. **No deben copiarse como si fueran contratos plug-and-play**.

## Modelo aritmético offline

`sypc_swap/offline_amm.py` aplica la desigualdad de producto constante del pool Spectrum a cantidades enteras, redondeando hacia abajo. Estudia el intercambio, no construye transacciones, no usa claves, no determina precios externos ni despliega contratos. Las comisiones del protocolo **siguen sin decidirse**; 997/1000 es un ejemplo de fixture.

## Puertas de seguridad

1. Revisar ruta de creación de tokens nativos y prefijos SYPC en el nodo; no basta la presencia del código.
2. Compilar el contrato atomic original con toolchain fijada y su suite original (dependencias y licencias registradas).
3. Adaptar script y serialización a red SYPC en copia aislada; volver a ejecutar pruebas y propiedades, no sólo el código heredado.
4. Una prueba end-to-end en **red privada autorizada**, con carteras sintéticas y validación independiente antes de órdenes reales.
5. Descartar uso de fondos reales y despliegue público hasta revisión de auditor externo.

### Fuentes

- Ergo Contracts: https://github.com/ergoplatform/ergo-contracts/tree/17ed58b39460e5520de56f615936d918603a3b9e
- Spectrum AMM: https://github.com/spectrum-finance/ergo-dex/tree/8fe94e1f8b4e1ab9402fca6fbc3955e3ad1415f7
- SYPC core: privado, `work/linux-node-lan-20261111`. Consultar el repositorio conectado y `CODEX_START_HERE.md` (no exponer ficheros privados).
