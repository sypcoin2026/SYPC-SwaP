# Fuentes abiertas y estrategia de reutilización

**La procedencia es parte del modelo de seguridad.** Se han copiado ocho archivos originales seleccionados (contratos de referencia y licencias) en `third_party/`, sin modificaciones ni integración ejecutable. No se han adaptado ni desplegado contratos ni ejecutores. Todos los hashes corresponden a referencias verificadas en GitHub el 2026-11-12, NO a aprobaciones de seguridad.

| Proyecto | Commit de referencia | Licencia declarada | Uso previsto |
| --- | --- | --- | --- |
| [spectrum-finance/ergo-dex](https://github.com/spectrum-finance/ergo-dex) | `8fe94e1f8b4e1ab9402fca6fbc3955e3ad1415f7` (master) | CC0 1.0 | Referencia de AMM, contratos y ejecución off-chain |
| [ergoplatform/ergo-contracts](https://github.com/ergoplatform/ergo-contracts) | `17ed58b39460e5520de56f615936d918603a3b9e` (develop) | CC0 1.0 | Ejemplos de intercambio y propiedades con verificación formal |
| [ergoplatform/ergo-dex](https://github.com/ergoplatform/ergo-dex) | `50596a92a465f52904b5d8015e8ae0d62e414176` (develop) | MIT | Referencia histórica de DEX de órdenes |

**Precaución:** estos commits son antiguos. No deben confundirse con versiones mantenidas, auditadas ni compatibles con SYPC. Revisar dependencias, incidencias, cambios posteriores, reportes de seguridad, restricciones de licencia por archivo, estado de mantenimiento y toolchain antes de integrar.

## Catálogo inicial

- Spectrum: `contracts/amm` contiene fuentes de contratos; revisar junto a `protocols` y dependencias reales.
- Ergo Contracts: `contracts/src/main/scala/org/ergoplatform/contracts/DexLimitOrder.scala` y `verified-contracts/src/main/scala/org/ergoplatform/contracts/AssetsAtomicExchange.scala`; los ejemplos de propiedades verificadas NO garantizan que un port posterior conserve la prueba.
- ErgoDEX: MIT exige mantener aviso de copyright y licencia en copias y partes sustanciales.

Las copias fueron cotejadas una a una con los blobs Git del origen tras publicarse en GitHub. [Inventario de hashes](../third_party/REFERENCES.json); la igualdad de bytes no es garantía de seguridad.

## Procedimiento obligatorio de adopción

1. Registrar URL, commit completo, licencia por componente, hash SHA-256 de archivo original e historial de actualizaciones.
2. Determinar superficie exacta a importar; prohibido el volcado masivo de dependencias sin auditoría.
3. Revisar código y pruebas *antes* de cambiar direcciones/prefijos, scripts, serialización o parámetros de red.
4. Definir comportamiento esperado mediante invariantes y propiedades; ejecutar suite original sin modificaciones.
5. Adaptar a red SYPC solo en rama experimental aislada; ejecutar pruebas de contrato y de nodo privado.
6. Comparar resultados originales y adaptados, documentar diferencias y registrar resultados reproducibles.
7. Revisión independiente antes de exponer fondos reales o habilitar contratos.

## Licencias y propiedad intelectual

Por ahora este repositorio contiene **documentación original, un modelo aritmético offline y fuentes originales de referencia no integradas**; no se ha elegido aún licencia de distribución propia. La publicación del repositorio por sí misma no autoriza reutilizar código de terceros sin respetar su licencia. La licencia de cada upstream no se transmite automáticamente a futuros archivos importados; los avisos y obligaciones deben documentarse en el momento de la incorporación.

**No vincular este proyecto a otros productos ni copiar datos privados del núcleo o de sus nodos.**
