# SYPC Reward — relevo completo para Codex (2026-11-14)

**Estado:** auditoría en curso, solo lectura, NO GO para activar SYPC-SwaP en una cadena con fondos.  
**Propósito:** preservar las observaciones reales del operador y continuar desde el punto exacto, sin repetir rondas de diagnóstico ni suponer coincidencias que no se han probado.  
**Privacidad:** extractos limitados a contadores, clases y hashes; no se incorporan rutas locales, direcciones de red, contraseñas, claves, argumentos de JVM, wallets ni configuración privada.

## 1. Repositorios, ramas y evidencia de CI

| Componente | Referencia | Estado verificado |
| --- | --- | --- |
| DEX público | [SYPC-SwaP PR #26](https://github.com/sypcoin2026/SYPC-SwaP/pull/26); rama `audit/reward-runtime-artifact-fingerprint-readonly-20261114` | DRAFT, no fusionar |
| Comprobador local | `tools/reward_runtime_artifact_fingerprint.py` del PR #26 | Solo lectura; analiza classpath del proceso Reward |
| Test del comprobador | `tests/test_reward_runtime_artifact_fingerprint.py` | 12 tests sintéticos por versión (Python 3.12 y 3.13), sin JVM real |
| CI de procedencia | [Actions #43541183640](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43541183640) | SUCCESS, commit `61b2a23381ad89d3754d3eed703ad3b142dc463e` |
| Core privado | [sypcoin-core PR #21](https://github.com/sypcoin2026/sypcoin-core/pull/21); rama `audit/syp-swap-reward-native-validation-20261114` | DRAFT, sin cambios de código de producción |
| Rama base del Core | `experiment/syp-testnet-reward-maturity-20261111` | Base de laboratorio, NO identidad demostrada del proceso local |
| Core test HEAD | `f2bdbca8ac4cc27392f7c2a78d695aedd074522b` | [CI #43539231991](https://github.com/sypcoin2026/sypcoin-core/actions/runs/43539231991): SUCCESS |
| Referencia de configuración | Java 11; `sigma-state_2.12-6.0.7.jar` | Se identificó en el inventario, sin atestación de toda la JVM |

**Identidad funcional:** se trata de la testnet privada **Reward** en uso, NO de la antigua V60. El launcher identificado por argumento principal fue `org.ergoplatform.sypcoin.SypRewardTestnetLauncher`. La testnet operativa no debe ser alterada como parte de la auditoría DEX.

**Límites del PR #21:** cinco tests de integración en clases `ErgoTransaction.statelessValidity`, `statefulValidity` y `ErgoState.execTransactions` de la rama Reward; validación con entradas y claves **sintéticas**, no con UTXO de la cadena activa. La CI actual exige ocho negativos atribuidos a la validación Core y dos negativos atribuidos a la generación de prueba del contrato; corrige falsos positivos por firmas ausentes o cambios posteriores a la firma. Esos PASS no demuestran validez de transacciones en los dos nodos activos.

## 2. Cronología reproducible de resultados del sobremesa

Los siguientes resultados proceden de salidas aportadas por el operador. Son **observaciones**, no verificaciones ejecutadas desde GitHub.

1. **Primera versión:** descarga con checksum correcto, pero error `SYPC_REWARD_PROVENANCE_FAIL:LAUNCHER_CODE_ARTIFACT_NOT_UNIQUE`. El código original no distinguía cero de varios artefactos. No inferir fallo del nodo.
2. **Segunda versión:** checksum correcto. Salida `SYPC_REWARD_SAFE_COUNTS`:
   `classpath_directories=9`, `classpath_entries=70`, `classpath_jar_files=61`, `classpath_missing_entries=0`, `launcher_candidates=4`, `sigma607_candidates=1`. Fin: `MULTIPLE_LAUNCHER_CODE_ARTIFACTS`.
3. **Tercera versión, búsqueda automática:** checksum correcto, pero `EXPECTED_EXACTLY_ONE_REWARD_LAUNCHER`. Un inventario independiente limitado a `/proc` observó tres procesos Java y **exactamente uno** con el argumento de clase Reward. El error del barrido automático queda por investigar; una condición transitoria es posible pero **no está demostrada**.
4. **Tercera versión, PID explícito observado localmente:** ejecución correcta del análisis del classpath, que terminó de modo seguro por cuatro candidatos divergentes. El PID concreto era un identificador temporal y se omite aquí; debe descubrirse de nuevo para futuras capturas.

En la última lectura válida se obtuvo:

```text
SYPC_REWARD_SAFE_COUNTS:
  classpath_directories      = 8
  classpath_entries          = 69
  classpath_jar_files        = 61
  classpath_missing_entries  = 0
  launcher_candidates        = 4
  sigma607_candidates        = 1
SYPC_REWARD_LAUNCHER_CANDIDATES:
  distinct_class_fingerprint_sets = 4
SYPC_REWARD_PROVENANCE_FAIL:MULTIPLE_LAUNCHER_CODE_ARTIFACTS
```

**Diferencia 70/9 frente a 69/8:** no se ha investigado. Puede deberse a otra captura del proceso o a cambios en el entorno; no afirmar la causa. Mantener las dos mediciones separadas, sin corregirlas por intuición.

## 3. Cuatro candidatos completos: SHA-256 de bytecode observado

Los índices son **base cero** dentro del classpath efectivo leído de la línea de comandos, no rutas ni identificadores de versión. En la última captura los cuatro son `class_directory`, por eso `jar_sha256=null`.

| Índice | SHA-256 `SypRewardTestnetLauncher.class` | SHA-256 `SypRewardTestnetLauncher$.class` |
| --- | --- | --- |
| **0** | `2b4f2cd193625b0b99d363985eb07b8fb68e0b5244511040daa8b3abe101b70d` | `a905fc9aa0eb74d1a6c7de7541e8631c22c276280aa7e545f942371509d2b091` |
| **2** | `4c4499417fc412f1bd322be8c94cc8223426bc16c8c4bf0b3cc44b417cdde9c4` | `6c7c6f2d0a3d677b01a2d7e8bc746428e0859879872d17d1f1fddb3eac3e91e1` |
| **3** | `4c4499417fc412f1bd322be8c94cc8223426bc16c8c4bf0b3cc44b417cdde9c4` | `7d582a1a5791a9b5b50819850e1f3138ac60b9ba76ccfec9bcdc8c5857b2eb08` |
| **4** | `08e4c0f8c5bcc02d8c334beccd32d3cf3970a3c75d7fef083e5e53da01b1dcda` | `db23b5a19a3c222a43da098efe0f546804c60d1d9bf31afb31c719a9a4e830b98` |

**Dato adicional:** el candidato del índice **4** incluía también la clase `ErgoState.class` con SHA-256 `2acf25913a6ec2519eea54ad60b2c281e8fbcf4508be99cb25762978ec57431a`. Los otros tres registros no la reportaron dentro del mismo directorio; eso **no** demuestra ausencia de esa clase en otras entradas del classpath.

**Deducciones sólidas:** hay cuatro pares de hashes de launcher distintos; índices 2 y 3 comparten la clase principal pero no la clase de objeto Scala. Es posible que correspondan a compilaciones distintas, pero **no están identificadas** sus ramas, fechas, commits ni procedencia. La precedencia habitual de un classpath Java sugiere el índice 0 en un cargador estándar, pero **no es prueba de la clase que cargó la JVM**. No llamar a ningún candidato «el activo» hasta obtener evidencia independiente.

## 4. Identidad de dependencia, compilación y discrepancia conocida

- Hash SHA-256 previamente observado del archivo de Sigma 6.0.7: `390bc91cb6201c26ae5309fd25c96f3e427343ed9b75968a2db96f365ca7d31b`. Se usa como valor esperado en el comprobador; no constituye firma de proveedor.
- SHA-256 del script V3 en commit `61b2a23381ad89d3754d3eed703ad3b142dc463e`: `479378f97a92639420fb61c7a9e3797b16605dde547215debfee79d51d9d3645`; el operador comprobó **OK** antes de ejecutar esa versión.
- La CI del Core detectó que `SypRewardTestnetConfig.scala` utiliza `Files.readString` (JDK 11) mientras el `build.sbt` conserva `scalac -release 8`. Para las cinco pruebas focales, la CI eliminó el flag únicamente **en su sesión SBT efímera**. No se cambió `build.sbt` ni el Core operativo. Investigar el impacto en reproducibilidad y comparar opciones reales del compilador.
- El PR #21 compara una rama de código *candidata* y no demuestra que la JVM en ejecución use el mismo bytecode ni idénticos parámetros de activación, estado o génesis.

## 5. Trabajo ya entregado a Codex: requisitos y prioridades

**A. Forense local solo lectura**

1. Redescubrir el proceso Reward por clase principal, sin asumir un PID persistente. Resolver, con un ensayo limitado y no invasivo, por qué la búsqueda automática dio `EXPECTED_EXACTLY_ONE_REWARD_LAUNCHER` cuando un inventario encontró un único Reward.
2. Localizar localmente las cuatro entradas del classpath, registrar metadatos y hashes (guardar información privada **solo localmente**); explicar qué aportó cada copia al classpath y si están desactualizadas.
3. Auditar duplicados de otras clases relevantes: `ErgoTransaction`, `ErgoState`, validación de encabezados, perfil/consenso Reward, emisión, interprete Sigma y configuración. **No afirmar que existan duplicados sin comprobarlo.**
4. Separar: (a) clase presente en classpath, (b) clase que el cargador usaría por precedencia y (c) clase **efectivamente cargada**, que puede no ser verificable por estos métodos. No usar Java Attach, `jcmd`, agentes ni depuradores sobre el proceso vivo.

**B. Evidencia de procedencia**

1. Pin exacto de repositorios, commit, JDK, Scala/SBT y dependencias.
2. Compilar o inspeccionar fuentes solo en espacio aislado, sin contaminar `target/` ni los artefactos del nodo operativo. Documentar precisión y límites de compilación reproducible.
3. Comparar SHA-256 de clases compiladas con las **ocho huellas** anteriores; separar discrepancias de código fuente y discrepancias de flags, herramientas o timestamps.
4. Si no se puede atestar el código cargado, declararlo **no demostrado** y explicar el siguiente ensayo mínimo seguro. No inventar equivalencias entre hashes/commits.

**C. Compatibilidad DEX**

- Revisar el PR #21 y las pruebas Sigma del PR #26 como referencias separadas.
- Confirmar qué se validó realmente para SELL, cancelación patrocinada, dos firmas Schnorr y preservación de tokens/native; distinguir negativos de Core frente a negativos de contrato.
- Mantener como pendientes: identidad real de JVM y cadena, tarifas y mínimos reales, storage rent, UTXO de la red, aceptación por productores y validadores independientes, mempool, doble gasto, reorganizaciones, reinicios y recuperabilidad.
- Planificar **red descartable separada** antes de cualquier prueba de contratos con activos; **no usar fondos reales ni carteras existentes**.

**D. Entrega en GitHub**

- Actualizar el PR #26 con resumen reproducible, defectos del comprobador corregidos, pruebas y evidencia de límites; actualizar el PR #21 o referenciarlo para la matriz de compatibilidad.
- Modificar solamente ramas experimentales/revisión. Si algo requiere cambios en producción/consenso, documentarlo como propuesta y solicitar autorización específica; **no ejecutarlo**.
- Mantener PR en DRAFT, sin merge ni lanzamiento.

## 6. Restricciones de la auditoría

No detener ni reiniciar nodos. No interrumpir minería ni cambiar GPU. No editar classpath activo, borrar JAR, limpiar directorios o DB de blockchain, tocar génesis/consenso/asignación monetaria, abrir puertos, elevar privilegios por rutina, ejecutar transacciones, firmar o acceder a carteras. No publicar datos identificables del host ni configuraciones, rutas o logs íntegros. No copiar snapshots privados al repositorio público.

Equipo productor = único minero autorizado; segundo equipo = receptor/validador sin minería. En las pruebas de SYPC-SwaP solo se trabaja con datos sintéticos y compilaciones aisladas.

## 7. Criterios de salida (NO confundir CI verde con release)

- [x] Hashes completos de los cuatro candidatos, con índices y datos de captura.
- [x] CI offline del comprobador y suite sintética Reward.
- [ ] Procedencia del código de los cuatro candidatos atribuida mediante evidencia.
- [ ] Comparación de clases contra una construcción pinneada y reproducible.
- [ ] Demostración explícita o declaración de no-demostración de la clase realmente cargada por el proceso.
- [ ] Identidad de configuración/activación del Core real comprobada sin mutarlo.
- [ ] Ensayos de cadena descartable con UTXOs reales, recuperación y dos validadores.
- [ ] Revisión humana independiente, reglas de protección de rama y aprobación de despliegue.

**Conclusión actual:** `SYPC_REWARD_PROVENANCE_FAIL:MULTIPLE_LAUNCHER_CODE_ARTIFACTS` es el resultado de seguridad correcto de un inventario ambiguo. No se ha probado vulnerabilidad de consenso, ni compatibilidad plena del DEX, ni coincidencia del binario local con el repositorio.

**Punto de entrada para Codex:** este documento + [procedencia de artefactos](REWARD_RUNTIME_ARTIFACT_PROVENANCE.md) + [PR #26](https://github.com/sypcoin2026/SYPC-SwaP/pull/26) + [Core PR #21](https://github.com/sypcoin2026/sypcoin-core/pull/21). No repetir diagnósticos ya completados; investigar la causa y documentar nueva evidencia.
