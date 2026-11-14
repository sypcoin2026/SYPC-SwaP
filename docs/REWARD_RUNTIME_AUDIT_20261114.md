# Auditoría de procedencia de Reward y compatibilidad con SYPC-SwaP

14 de noviembre de 2026. **La procedencia de las clases base en disco se reprodujo. La carga efectiva del productor sigue inferida. La compatibilidad acreditada para Swap sigue siendo de laboratorio.**

## 1. Las cuatro compilaciones

La JVM del productor arrancó el 14/11 con OpenJDK 11.0.33 de Ubuntu y `SypRewardTestnetLauncher`. La lectura de `/proc` encontró 69 entradas, 8 directorios, 61 JAR y 0 ausencias. Cuatro capas anteceden las 65 entradas del classpath base. Las fechas de la tabla están en CET y las huellas corresponden a los bytes en disco.

| Índice | Última escritura de la pareja | Tamaño en bytes: launcher / módulo | Procedencia |
| --- | --- | --- | --- |
| 0 | 14/11, minutos antes del arranque | 3.772 / 35.211 | Capa LAN para el arranque de escritorio. La receta Scala directa produjo launcher, permiso y controlador de red. Las 37 clases coinciden al compilar las fuentes locales y 36 coinciden con las fuentes del commit privado `47d4ccefff7356be5e401a9da74f12e28c4f25bc`. |
| 2 | 12/11, después del índice 3 | 3.466 / 27.846 | Capa móvil posterior de 8 clases. Contiene la variante del launcher con cambios en la comprobación de argumentos de `main` y su permiso. La fuente histórica exacta queda pendiente. |
| 3 | 12/11, 16 minutos antes del índice 2 | 3.466 / 27.862 | Primera capa móvil de 8 clases, ampliada a 14 con el lector Reward. Los JAR intermedios del paquete Android conservan los bytes de su módulo del launcher. La fuente histórica exacta queda pendiente. |
| 4 | 11/11 | 3.018 / 24.431 | Salida incremental de SBT del checkout Reward. Las cuatro clases del launcher, incluidas las dos de `Session`, coinciden con la construcción aislada de las fuentes del commit base del PR #21. |

| Índice | SHA-256 launcher | SHA-256 módulo Scala |
| --- | --- | --- |
| 0 | `2b4f2cd193625b0b99d363985eb07b8fb68e0b5244511040daa8b3abe101b70d` | `a905fc9aa0eb74d1a6c7de7541e8631c22c276280aa7e545f942371509d2b091` |
| 2 | `4c4499417fc412f1bd322be8c94cc8223426bc16c8c4bf0b3cc44b417cdde9c4` | `6c7c6f2d0a3d677b01a2d7e8bc746428e0859879872d17d1f1fddb3eac3e91e1` |
| 3 | `4c4499417fc412f1bd322be8c94cc8223426bc16c8c4bf0b3cc44b417cdde9c4` | `7d582a1a5791a9b5b50819850e1f3138ac60b9ba76ccfec9bcdc8c5857b2eb08` |
| 4 | `08e4c0f8c5bcc02d8c334beccd32d3cf3970a3c75d7fef083e5e53da01b1dcda` | `db23b5a19a3c222a43da098efe0f546804c601d9bf31afb31c719a9a4e830b98` |

La cuarta huella de módulo escrita en el encargo tenía 65 caracteres. El valor de 64 caracteres de la tabla coincide con el archivo leído, la compilación y el relevo conservado previamente. Los índices 2 y 3 comparten tres de las cuatro clases de la familia. La descompilación, normalizada para eliminar índices de tabla de constantes y números de línea, aisló la diferencia de instrucciones del módulo en `main`. El lector del índice 3 usa una ruta de carga por recurso y `readAllBytes` con UTF-8 donde la base usa `Files.readString`. Esto explica diferencias de fuente aparte de cualquier opción del compilador. La captura antigua de 70 entradas sigue siendo un dato histórico de otra observación. [Relevo previo](REWARD_RUNTIME_CODEX_HANDOFF_20261114.md).

Hay 48 nombres de clase Core presentes en más de una entrada. El módulo del permiso de consenso tiene cuatro huellas. `NetworkController` se duplica en 0/4 y `ErgoApp` en 1/4, con bytes distintos. En 3/4 coincide la clase estática de `SypRewardTestnetConfig` y difiere el módulo. La capa 1 corresponde a pagos. La reproducción con las fuentes disponibles igualó 17 de sus 19 clases, con divergencia en las dos de `SypRewardPaymentPlan`. En la captura, `ErgoTransaction`, `ErgoState`, `UtxoState`, `HeadersProcessor` y el intérprete de la cartera tienen una copia por nombre. Los paquetes de Sigma carecen de duplicación. El JAR Sigma 6.0.7 del índice 23 coincidió byte a byte con Maven Central y con un descriptor abierto por la JVM según dispositivo e inodo. [Sigma State 6.0.7 en Maven Central](https://central.sonatype.com/artifact/org.scorexfoundation/sigma-state_2.12/6.0.7).

## 2. Procedencia y reproducción

| Ámbito | Referencia comprobada | Resultado |
| --- | --- | --- |
| Checkout local | HEAD de trabajo con las fuentes Reward añadidas en el índice de Git | El identificador local aparece abreviado en el metadato `Version$` de la salida instalada. El árbol local de trabajo y el commit del repositorio son objetos distintos. |
| Fuentes Core y build de referencia | `9e014bfed70ea47d0f1939b2f7246917f82c3988`, árbol Git `b24a9dc9c04211cfce720bd02f9b78b22b5dd79f` | 951 archivos de fuentes, recursos y build cotejados por blob Git contra el repositorio privado. Compilación de producción contrastada con las entradas 4 a 7. |
| Rama Reward remota | `47d4ccefff7356be5e401a9da74f12e28c4f25bc` | Conserva los mismos inputs del build estándar y añade fuentes de la capa LAN. La variante local del controlador de red sustituye un literal de identificación de arranque, lo que explica la única diferencia de esa capa. |
| PR Core #21 | Revisión pedida `f2bdbca8ac4cc27392f7c2a78d695aedd074522b`, HEAD observado `896c7da951febcec2d5c3ed5f4dc2da68b0e1960` | El avance añade documentación. El run de la revisión pedida hizo checkout del merge de prueba `59f3557d1913ab03a5cc7b11e3ac3117e7da0744`, con el mismo árbol Git que `f2bdbca8`. |
| PR Swap #26 | Revisión pedida `61b2a23381ad89d3754d3eed703ad3b142dc463e`, revisión inicial de esta auditoría `797b7c8c54710945f93020c1cbaa4f244464b851` | El avance previo añade el relevo. Las correcciones de procedencia viven en la rama de auditoría de este PR. |

[Base del Core](https://github.com/sypcoin2026/sypcoin-core/commit/9e014bfed70ea47d0f1939b2f7246917f82c3988) · [Capa LAN en el Core](https://github.com/sypcoin2026/sypcoin-core/commit/47d4ccefff7356be5e401a9da74f12e28c4f25bc) · [PR Core #21](https://github.com/sypcoin2026/sypcoin-core/pull/21) · [PR Swap #26](https://github.com/sypcoin2026/SYPC-SwaP/pull/26).

### Construcción base

Usar Java 11.0.33, Scala 2.12.20, SBT 1.11.1 y Sigma 6.0.7 con los archivos `build.sbt` de la raíz y cada subproyecto, `project/` y el árbol fijado. Los destinos, cachés y temporales de la auditoría estaban en un directorio separado. Las dependencias se aprovisionaron en la caché de auditoría y se compiló sin red. Estos son los perfiles probados en el mismo árbol de fuentes.

```bash
SIGMASTATE_VERSION=6.0.7 sbt -batch 'Compile / compile'

SIGMASTATE_VERSION=6.0.7 sbt -batch \
  'set Compile / compile / scalacOptions := (Compile / compile / scalacOptions).value.filterNot(Set("-release", "8"))' \
  'Compile / compile' 'export Compile / fullClasspath'

SIGMASTATE_VERSION=6.0.7 sbt -batch \
  'set Compile / compile / scalacOptions := (Compile / compile / scalacOptions).value.filterNot(Set("-release", "8")) ++ Seq("-release", "11")' \
  'Compile / compile'
```

El primero falló en el proyecto raíz por `Files.readString` (desde Java 11) y `ProcessHandle` (desde Java 9), entre los diagnósticos principales. Los otros dos compilaron las clases de producción. El segundo aplica el ajuste de la CI de #21 únicamente en la sesión de SBT. El tercero reproduce `-release 11`, que registra el análisis incremental del Core instalado para Scala en el proyecto raíz. El mismo análisis registra `--release 8` para Java. Las dos compilaciones exitosas coincidieron para todas las clases salvo el metadato generado `Version$`. La versión mayor 52 de las cuatro familias de launcher describe su formato de clase y permite referencias a APIs que requieren una JVM posterior. [Files en Java 11](https://docs.oracle.com/en/java/javase/11/docs/api/java.base/java/nio/file/Files.html#readString(java.nio.file.Path)) · [ProcessHandle](https://docs.oracle.com/en/java/javase/11/docs/api/java.base/java/lang/ProcessHandle.html).

Para reproducir el cotejo, comparar por módulo y nombre relativo con SHA-256, y comparar los JAR en orden. Coincidieron **1.688/1.689 clases, 68/68 recursos y 61/61 JAR en el mismo orden**. La única diferencia en la base, `org.ergoplatform.Version$`, era la constante de versión generada con los metadatos Git. Una compilación focal del generador con el valor observado reprodujo también esa clase. Esta segunda prueba aísla la causa de la diferencia.

Para la capa LAN, usar la receta del commit `47d4ccef`. Con Java 11 y el compilador Scala 2.12.20, compilar los tres archivos Scala ordenados por nombre con `scala.tools.nsc.Main`, con una copia del índice 3 delante de una copia de las 65 entradas base, y un directorio de salida nuevo. Comparar las huellas por nombre de clase. La variante local del literal de arranque es necesaria para reproducir `NetworkController.class`. Las cuatro huellas del launcher dan el mismo resultado con ambas variantes. La reconstrucción con las fuentes móviles disponibles produjo una tercera pareja de launcher. Para resolver la procedencia exacta de 2 y 3, la única comprobación adicional es aplicar `git hash-object` a las fuentes y a la receta de un respaldo histórico, si aparece, y cotejar esos blobs con el árbol de origen. El cotejo de bytes se haría tras compilar esa receta en aislamiento.

### Código que cargó la JVM

- **Confirmado:** proceso Java del productor con la clase principal Reward, cuatro conjuntos de bytecode en disco y Sigma 6.0.7 con descriptor abierto. El PID y los ticks de arranque coincidieron al inicio y al final del inventario.
- **Observado en una JVM independiente:** Java 11, copias de las 69 entradas y `Class.forName` sin inicializar las clases de aplicación. El `CodeSource` del cargador de aplicación tomó launcher, permiso y controlador de red del índice 0, `ErgoApp` del 1, lector Reward del 3, estado del 4, transacción del 5, intérprete de la cartera del 7 y Sigma del 23. Se guardó también la traza de carga de esa JVM.
- **Inferido con confianza alta para el productor:** los mismos orígenes bajo la delegación habitual, el classpath observado, la antigüedad de los artefactos y el enlace LAN instalado antes del arranque. La evidencia de `/proc`, los JAR abiertos y los registros existentes carece de un `CodeSource` o una traza de carga del productor. La identidad de cada clase efectivamente cargada y la configuración de activación de cadena quedan sin atestación directa. [Delegación de ClassLoader](https://docs.oracle.com/en/java/javase/11/docs/api/java.base/java/lang/ClassLoader.html) · [Registro de carga de Java 11](https://docs.oracle.com/en/java/javase/11/tools/java.html).

## 3. Compatibilidad SYPC-SwaP

| Propiedad | Evidencia | Pendiente |
| --- | --- | --- |
| eUTXO, ErgoScript y Sigma 6.0.7 | El #21 llama a `ErgoTransaction.statelessValidity`, `statefulValidity` y `ErgoState.execTransactions` con cajas y cabeceras sintéticas Reward. Comprueba serialización del mensaje firmado. | Transacciones de punta a punta con el perfil efectivo, UTXO de una cadena descartable, productor y segundo validador. |
| SELL | Se acepta el llenado financiado, con precio, colateral, pago al vendedor y referencia R4 a la orden. Se rechazan pago insuficiente, destinatario incorrecto, R4 erróneo y prueba del comprador ausente. | Aceptación en mempool y bloque. |
| BUY | El intérprete aislado de Sigma 6.0.7 en Swap acredita un llenado y siete rechazos sobre token, cantidad, destinatario, R4 y orden de salidas. | BUY firmado por el input que corresponda, validación Core Reward y cadena. |
| Schnorr y cancelación patrocinada | Se generan dos pruebas no vacías para dos entradas sobre el mismo mensaje, con la misma clave sintética de propietario. Core acepta el caso válido y rechaza la prueba de sponsor ausente. Dos negativos adicionales aíslan la imposibilidad de generar la prueba SELL con fee excesivo o script de fee incorrecto. | Coste real, recuperabilidad y aceptación tras reorg. |
| Tokens y conservación | Se verifican los balances nativo y de tokens en los positivos. Se rechazan el token de salida falso y el input duplicado. | Riesgos de concurrencia y doble gasto, renta, límites de tamaño y condiciones de la versión de script activa. |
| Fees y cajas | El positivo usa la proposición de fee de la fixture Reward. El negativo de dust vuelve a firmarse y conserva el balance nativo. Se ejercita el rechazo de la caja de valor 1. | El mínimo de comisión de `ErgoMemPool.process`, los parámetros efectivos y el coste a nivel de bloque requieren pruebas propias. |

La CI del Core en `f2bdbca8` registra 5 pruebas, 2 casos positivos, 8 rechazos del validador y 2 rechazos de generación de prueba. Varios negativos pasan por métodos que devuelven éxito/fallo agregado, por lo que atribuirlos a una regla concreta exige revisar el código y la mutación. El HEAD posterior del PR también pasó. [CI Core de la revisión pedida](https://github.com/sypcoin2026/sypcoin-core/actions/runs/43539231991) · [CI Core del HEAD observado](https://github.com/sypcoin2026/sypcoin-core/actions/runs/43550434549) · [BUY en PR #23](https://github.com/sypcoin2026/SYPC-SwaP/pull/23) · [CI Sigma BUY](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43528024386) · [CI de cancelación patrocinada](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43531691519).

## 4. Riesgos y corrección

| Gravedad | Evidencia y alcance |
| --- | --- |
| Alta | La precedencia de capas mutables cambia la composición ejecutable de Core. Además del launcher, afecta al permiso, el controlador de red y el código de arranque de la aplicación. Una coincidencia parcial acredita archivos concretos, con exposición a atribución errónea del proceso. |
| Alta para el ensayo con activos | BUY y el ciclo de vida completo del DEX están pendientes de Core y cadena. Aceptar una fixture sintética como evidencia de despliegue dejaría sin verificar comisiones, renta y aceptación por validadores. |
| Media | La compilación depende de ajustes de sesión JDK y la variante local del controlador. La etiqueta Git de `Version$` por sí sola describe la versión generada. |
| Media | El comprobador anterior buscaba el nombre principal en cualquier argumento, deduplicaba entradas y aceptaba ciertas causas de falsa confianza como un único módulo sin su clase estática, un classpath incompleto o una dependencia con el nombre correcto sin pin por defecto. La causa histórica concreta del rechazo automático previo queda sin captura que la demuestre. |

El [verificador actualizado](../tools/reward_runtime_artifact_fingerprint.py) fija Sigma por defecto, comprueba la identidad del proceso antes y después de la lectura, conserva el orden, reconoce las clases superpuestas y emite diagnósticos redactados. En modo comparativo exige un manifiesto fijado, comprueba el classpath completo y hashes seleccionados del JDK. [Pruebas adversariales](../tests/test_reward_runtime_artifact_fingerprint.py) · [Procedimiento del manifiesto](REWARD_RUNTIME_ARTIFACT_PROVENANCE.md).

**Paso mínimo siguiente:** construir una sola distribución descartable desde fuentes fijadas, con una definición por clase Core/Sigma. Fijar el manifiesto en el build, montar la distribución de solo lectura y capturar la traza de carga desde el arranque de los dos procesos de laboratorio. Con ese artefacto, probar BUY y SELL firmados y cancelación patrocinada con UTXO sintéticos de la nueva cadena y verificar aceptación por mempool, bloque y segundo validador.
