# Verificación de procedencia de Reward

El comprobador de este PR sirve para inventariar el classpath de Reward en Linux y comparar sus archivos con los de una compilación independiente. La [auditoría del 14 de noviembre](REWARD_RUNTIME_AUDIT_20261114.md) recoge los cuatro artefactos del productor, su reconstrucción y el alcance de las pruebas de Swap.

## Inventario de solo lectura

```bash
python3 -B tools/reward_runtime_artifact_fingerprint.py
```

Ejecutar con el usuario de Reward. El script descubre la JVM por su clase principal exacta. Se puede indicar `--pid` cuando ya se conoce el proceso por evidencia externa. Lee metadatos de `/proc` y de los archivos del classpath. Comprueba en memoria y sin emitir valores si el entorno inicial contiene opciones que pueden cambiar la carga. La salida contiene contadores, posiciones, identificadores de clase conocidos y huellas. Un fallo de lectura devuelve un código fijo.

El inventario respeta el orden y las repeticiones del classpath. Exige las dos clases de entrada del launcher y el SHA-256 de Sigma 6.0.7 cotejado con Maven Central. Rechaza duplicados para las clases vigiladas e indicios de redirección de la carga mediante comodines, agentes, opciones JVM ambiguas o metadatos de JAR. La salida de un classpath ambiguo incluye `SYPC_REWARD_DISK_EVIDENCE` para cotejar sus clases, con código de salida 2.

## Comparación con una compilación independiente

Preparar un checkout fijado por commit, validar la procedencia de sus inputs y compilar en un directorio nuevo. Guardar únicamente el valor de `export Compile / fullClasspath` en un archivo local de una línea, con todas las entradas absolutas y en el orden de despliegue. Si el artefacto combina fuentes de distintos commits o módulos, la receta y sus huellas forman parte de la evidencia firmada de la compilación. El campo `core_commit` identifica la base que indica el constructor.

```bash
python3 -B tools/reward_runtime_artifact_fingerprint.py \
  --build-classpath-file "$BUILD_CLASSPATH_FILE" \
  --build-java "$JAVA_HOME/bin/java" \
  --core-commit "$CORE_COMMIT" > "$REWARD_BUILD_MANIFEST"

sha256sum "$REWARD_BUILD_MANIFEST"
```

El manifiesto registra, en orden, el tipo y SHA-256 de cada JAR y de todo el árbol de cada directorio del classpath, incluidos los recursos. Registra también una huella del nombre base de cada JAR, que puede afectar al nombre del módulo o a la búsqueda de recursos. El hash de un directorio incorpora su estructura, los nombres relativos y el SHA-256 de cada archivo, en orden por bytes. También registra hashes del lanzador Java, `libjvm.so`, la imagen de módulos y el descriptor de Java 11. El modo estricto exige rutas canónicas, rechaza enlaces simbólicos dentro de los árboles y rechaza duplicados de las clases Core y Sigma, aunque los bytes coincidan.

Publicar o entregar mediante un canal de confianza el hash del manifiesto junto con la evidencia de compilación correspondiente. Verificar la instalación contra ese hash, obtenido independientemente de la máquina o instalación que se examina.

```bash
python3 -B tools/reward_runtime_artifact_fingerprint.py \
  --manifest "$REWARD_BUILD_MANIFEST" \
  --expected-manifest-sha256 "$TRUSTED_MANIFEST_SHA256"
```

`artifact_manifest_match: true` acredita que la captura en disco concuerda con los bytes descritos por el manifiesto fijado. La vinculación con el commit depende de la evidencia externa de compilación. El programa conserva `git_commit_verified`, `runtime_class_loading_verified` y `chain_or_consensus_verified` en `false`. Para una ejecución futura, usar artefactos de solo lectura, registrar el hash firmado del manifiesto e iniciar la JVM descartable con traza `class+load`. Vincular en esa evidencia el arranque, los orígenes observados de las clases Core/Sigma y la identidad y parámetros de la cadena comprobados por separado.

El modo manifiesto lee todo el classpath y la imagen de módulos. Está previsto para instalaciones preparadas para auditoría y requiere artefactos estables durante la captura. La traza y los metadatos propios de la máquina deben conservarse en el entorno privado. [Registro de carga de clases en Java 11](https://docs.oracle.com/en/java/javase/11/tools/java.html#GUID-0F2D31A1-3B33-4FE5-8197-46F2B6DC5051).
