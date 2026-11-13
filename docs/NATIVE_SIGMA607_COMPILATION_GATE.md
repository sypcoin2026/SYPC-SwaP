# SYPC Swap — primer gate nativo de compilación Sigma 6.0.7

**Fecha:** 14/11/2026 · **Estado:** CANDIDATO DE PRUEBA, sin despliegue.

## Objetivo

Cerrar la brecha de *compilación* entre las siete suites históricas que usan `Sigma 4.0.5` y la versión `sigma-state 6.0.7` que `sypcoin-core/build.sbt` declara **por defecto**. Este gate **no ejecuta el validador nativo de SYPC, no genera transacciones completas y no demuestra compatibilidad de consenso**. Los resultados antiguos 4.0.5 se conservan exclusivamente como referencia histórica.

## Implementación aislada

Un subproyecto Scala 2.12.20/SBT 1.11.1 vive exclusivamente en `research/native6/`, con dependencia directa `org.scorexfoundation:sigma-state_2.12:6.0.7`. No importa ni modifica código privado, consenso ni bases de SYPC Core.

- `NativeSigma607Compile` utiliza la API `sigma.compiler.SigmaCompiler`, `CompiletimeIRContext` y `sigma.ast.ErgoTree` de la versión 6.0.7.
- Comprueba que la clase del compilador viene del **JAR 6.0.7 efectivo**, no solo de la cadena escrita en `build.sbt`.
- Compila **seis** scripts experimentales originales de `research/ergo_script/`, en contextos nuevos, con datos **sintéticos**.
- Repite compilación para comprobar determinismo, hace round-trip de serialización, fija las diferencias al mutar un parámetro económico y exige rechazar código sintácticamente inválido.
- Los resultados imprimen la huella SHA-256 del ErgoTree para que los dos runners puedan compararse y, tras revisión, se fije un pin en una regresión posterior.
- CI en Ubuntu 22.04 y 24.04 con Java 11, acciones y sbt launcher fijados a SHA.

## Niveles de evidencia (no mezclar)

1. `SIGMA4_REFERENCE_PASS`: prueba histórica del contrato en el intérprete Spectrum 4.0.5.
2. `SIGMA6_COMPILER_PASS`: **solo** compilación y serialización reproducibles de contratos en la biblioteca 6.0.7.
3. `SYPC_NATIVE_INTERPRETER_PASS`: ejecutar scripts y pruebas de firmas/costes con el núcleo exacto y runtime efectivo SYPC, **aún sin implementar**.
4. `SYPC_COMPLETE_TX_PASS`: construir/gastar UTXO con tarifas y conservación reales, **pendiente**.
5. `SYPC_TWO_NODE_PASS`: nodos validadores independientes, reorg/restart/cancelación, **pendiente**.

El Auditor v0.1 sigue devolviendo solamente `PASS_EVIDENCE_INTEGRITY_ONLY`; ninguno de estos niveles autoriza fondos ni desplegar el DEX.

## Próximas comprobaciones obligatorias

- Resolver la versión **real** de JAR y dependencias en el nodo que opere la testnet privada. `sypcoin-core` admite override `SIGMASTATE_VERSION`; este gate por sí solo no identifica el runtime del nodo.
- Probar los mismos contratos en el intérprete `ErgoInterpreter` y contexto de transacción de Core 6.0.7 (firma, opcodes, coste, contexto/cabeceras, parámetros de activación); **sin modificar** las reglas para hacerlo funcionar.
- Comparar con los scripts de referencia: hashes de ErgoTree entre 4.0.5/6.0.7 **no tienen por qué ser idénticos**; toda divergencia requiere explicación y regresión.
- Reproducir ataques de token falso, firma ausente, gastos inconsistentes, fee máxima, overflow, cancelación irrecuperable, doble gasto y reorganización en una red descartable.
- Exigir revisión independiente, notificación de incidencias y aprobación explícita antes de tocar la testnet privada existente.

## Invocación en una copia local de código (NO en equipos de producción)

```bash
cd research/native6
sbt -batch 'runMain org.sypcoin.swap.NativeSigma607Compile ../ergo_script'
```

No se crean ni se cargan claves privadas; las claves de la fixture son constantes públicas de ensayo y **no deben reutilizarse fuera del laboratorio**. El harness no abre sockets ni usa APIs REST; `sbt` puede descargar dependencias durante la compilación, por lo que no se considera una sesión sin Internet hasta precargar y aislar los artefactos.

**NO-GO** para testnet actual hasta el ensayo nativo con transacciones completas y liveness con sponsor. Todos los PR experimentales permanecen en borrador.
