# SYPC Reward — huellas locales de los artefactos de la JVM (SOLO LECTURA)

Fecha: 2026-11-14. Estado: **laboratorio / NO GO**. Válido para el productor actual
con launcher \`org.ergoplatform.sypcoin.SypRewardTestnetLauncher\`, **no V60**.

## Objetivo

El test nativo de [sypcoin-core PR #21](https://github.com/sypcoin2026/sypcoin-core/pull/21)
valida transacciones sintéticas contra las clases Reward de GitHub. El inventario
previo identificó Java 11 y Sigma 6.0.7 en el nodo real, pero **no identifica el
commit del código que ese proceso está ejecutando**. Esta prueba NO equivale a
un ensayo de cadena ni a una atestación de procedencia del binario.

\`tools/reward_runtime_artifact_fingerprint.py\` identifica exactamente un
proceso Java cuyo argumento principal sea la clase Reward, obtiene su classpath
de \`/proc\` SIN mostrar argumentos ni rutas, y calcula SHA-256 de:

- JAR Sigma 6.0.7 que figura en el classpath.
- JAR que contiene la clase \`SypRewardTestnetLauncher\`, o los bytes de la
  clase si se carga desde directorio, junto a un subconjunto de clases Core
  cuando aparezcan en el mismo directorio.

El resultado **omite argv, variables de entorno, configuración, IP, claves,
wallets, rutas de usuario y datos privados**. No usa red, shell, procesos
subordinados, GPU, Java Attach, REST o escrituras. No lee el estado del nodo,
ni afirma nada sobre el compilador/reproducibilidad del JAR.

## Ejecución en el sobremesa, SIN detener ni reiniciar el nodo

Tras descargar y revisar el script de la rama experimental, ejecutar con el
usuario que ejecuta Reward, desde una copia local:

\`\`\`bash
python3 -B tools/reward_runtime_artifact_fingerprint.py \
  --expected-sigma-sha256 \
  390bc91cb6201c26ae5309fd25c96f3e427343ed9b75968a2db96f365ca7d31b
\`\`\`

El SHA de Sigma es **la huella observada en el inventario del 14/11/2026**,
no una atestación independiente de publicación de sigma-state. Si ha cambiado,
el script falla en vez de aceptarlo silenciosamente.

Si hay más de un launcher en el mismo equipo, se debe investigar la causa
antes de continuar. No seleccionar arbitrariamente el primero; si el proceso
correcto está identificado de forma independiente, se puede indicar
\`--pid 12345\` (usar el PID real, nunca inventado).

## Interpretación

\`LOCAL_ARTIFACT_HASHES_ONLY\` significa que obtuvimos huellas locales de
artefactos del classpath. \`git_commit_verified: false\` y
\`chain_or_consensus_verified: false\` son deliberadamente **siempre false**.

Para demostrar que el Core activo coincide con el código examinado, se
necesita una compilación reproducible o una cadena de procedencia firmada,
con hashes que coincidan, más los parámetros reales del perfil y la identidad
de génesis. Si el código se carga desde directorios de clases, los hashes
de unas pocas clases no prueban el directorio completo ni posibles cargas
dinámicas. No usar estos resultados para desplegar SYPC-SwaP o mover fondos.

## Protección y limitaciones

- Solo Linux; lee \`/proc/<pid>/cmdline\`, \`/proc/<pid>/cwd\` y artefactos
  del classpath, nunca \`/proc/<pid>/environ\`.
- No se sube el resultado completo a GitHub ni se crea archivo automático.
  Si se comparte una captura, revísese manualmente antes de publicarla.
- Un proceso sin classpath explícito, JAR ausente, hashes Sigma inconsistentes,
  más de un launcher o artefacto ambiguo debe causar fallo cerrado.
- Se prueban en CI únicamente árboles \`/proc\` sintéticos; CI no accede al
  ordenador del usuario ni prueba la ejecución en el nodo real.
- El proceso podría tener clases inyectadas o cargadas dinámicamente; tampoco
  se prueba inmutabilidad temporal del JAR. Para operación real hay que
  preparar una cadena separada y desechable, con UTXO nuevos.
