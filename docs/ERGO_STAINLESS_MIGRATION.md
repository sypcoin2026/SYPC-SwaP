# Bloqueo de pruebas formales de Ergo original (12/11/2026)

## Observación confirmada

El proyecto `ergoplatform/ergo-contracts` a commit `17ed58b39460e5520de56f615936d918603a3b9e` utiliza:

- Scala `2.12.9`, sbt `1.3.4`, `sbt-stainless 0.6.1` y bibliotecas `sigma-state 3.2.1`.
- Repositorios Bintray históricos y un repositorio HTTP (`logicrunch.research.it.uu.se`).
- Intento real de ejecutar `verifiedContractsTests/testOnly *AssetsAtomicExchangeCompilationTest` en un entorno CI separado: **FAIL antes de cargar el proyecto** por plugin `ch.epfl.lara:sbt-stainless:0.6.1` no descargable.
- Logs de la ejecución fallida: [GitHub Actions 43237243130](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43237243130). El checkout de commit y los hashes originales fueron verificados.

**No es fallo de las propiedades del contrato**: el test formal ni siquiera arrancó. Por tanto, no existe evidencia nueva de verificación formal reproducida para SYPC.

## Por qué no basta actualizar la versión

El proyecto Stainless actual documenta que **ya no admite la implementación frontal de Scala 2**; sus versiones recientes se centran en Scala 3. Migrar exigirá revisar las firmas, la representación de sigma-props, las pruebas originales, el modelo y las obligaciones de demostración. No basta sustituir `0.6.1` por un número más alto.

Referencias:
- https://github.com/epfl-lara/stainless
- https://www.scala-sbt.org/1.x/docs/Bintray-For-Plugins.html

## Estrategia sin reducir seguridad

**Track A — compilación/ejecución del contrato:** usar el banco de pruebas aislado de Spectrum con Sigma 4.0.5; no afirmar equivalencia semántica con el original. Ya hay 4 tests Scala compilando candidatos, sin ejecución de transacciones.

**Track B — propiedades formales:** extraer especificación de las propiedades de compra, venta, cancelación y conservación de activos; portar a un entorno soportado de Stainless para **volver a demostrar las propiedades**, junto con evidencias reproducibles. No reutilizar un viejo certificado como si validara código nuevo.

**Track C — consenso SYPC:** ejecutar contratos y pruebas en el nodo SYPC real, con claves desechables, cadena privada aislada, dos nodos validadores independientes y evidencias inmutables (hashes de scripts, inputs, outputs, logs, altura y state root). Ningún cambio de consenso sin autorización expresa.

## Política de dependencia

- No activar repositorios HTTP inseguros para «hacer pasar» CI.
- No descargar binarios desconocidos sin procedencia y hashes.
- No eliminar el test formal fallido y presentarlo como aprobado.
- No mezclar CI de investigación con un gate de mainnet.
- Revisión externa de dependencias y de contratos antes de fondos reales.

**Estado actual:** original formal **BLOQUEADO por toolchain**; candidatos ErgoScript **COMPILAN en banco Sigma**; compatibilidad real SYPC **NO DEMOSTRADA**.
