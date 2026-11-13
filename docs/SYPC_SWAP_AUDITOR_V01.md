# SYPC Swap Auditor — arquitectura de seguridad y núcleo v0.1

**Fecha de diseño:** 13/11/2026  
**Estado:** PROTOTIPO AUDITOR OFFLINE, no integrado, no desplegado, no firma ni accede a fondos.  
**Base:** rama `audit/sell-asset-bound-sponsor-20261112` / PR #19.  
**Ubicación:** `tools/sypc_swap_auditor.py`; pruebas `tests/test_sypc_swap_auditor.py`.

## 1. Corrección de la discrepancia de Sigma

En `sypcoin-core` `build.sbt` fija `sigma-state 6.0.7` por defecto (aunque la variable de entorno `SIGMASTATE_VERSION` permite modificar la versión efectiva). El harness histórico de Spectrum Finance/ergo-dex se fijó en `Sigma 4.0.5` para **investigación y regresión sobre sus contratos heredados**.

**Decisión P0:** conservar el entorno 4.0.5 únicamente como referencia, perfectamente identificado como tal; **no constituye validación del motor SYPC**. Las pruebas de compatibilidad y autorización nativas deben utilizar exactamente el motor, versión de Sigma, serialización, ErgoTree, reglas de coste, contexto y parámetros de génesis de los binarios SYPC realmente ejecutados. Verificar también hashes de JAR y resolución real de dependencias, no solo el número escrito en `build.sbt`.

El Auditor v0.1 **rechaza un informe de compatibilidad nativa marcado con 4.0.5** cuando la política aprobada fija 6.0.7. No cambia una sola dependencia, ErgoScript, regla de consenso ni proceso.

## 2. Por qué existe el auditor

Un test puede pasar por error, dar un resultado positivo con una transacción sintética que el nodo rechazaría, mezclar cadenas, aceptar información antigua o no probar el contrato que acabamos de compilar.

El sistema separará:
1. **Ejecutor / wallet de ensayo:** crea una operación en una cadena descartable con claves de test y puede solicitar su inclusión.
2. **Observador(es) de nodo:** reportan eventos desde canales READ-ONLY independientes. El receptor nunca mina.
3. **SYPC Swap Auditor:** valida identidad de cadena, huellas, coherencia temporal, evidencia y reglas independientes, sin capacidad de firma, envío, minería ni administración.
4. **Revisión humana:** decide qué fallos tienen impacto, qué pruebas adicionales hacer y qué parche mínimo aprobar.

**Nunca confiar en un PASS autorreferencial.** El auditor debe comparar artefactos y evidencias independientes. En v0.1 los hashes solo demuestran integridad relativa al manifiesto; no autentican al productor de evidencia. Tampoco se comprueban aún proofs AVL+, scripts on-chain, firma de UTXOs, firmas de logs o autenticidad de nodos.

## 3. Núcleo implementado ahora (v0.1)

El script `tools/sypc_swap_auditor.py` solo lee tres entradas de una carpeta local:
- `--policy`: identidad y commit de Core/Swap, génesis, versión Sigma nativa autorizada, huella del ErgoTree candidato. Esta política debe ser fijada manualmente desde datos **verificados externamente** y conservarse fuera de Git.
- `--run`: informe de ensayo con identificador, fase y checks esperados.
- `--evidence-dir`: logs `.log`/`.txt`/`.json` individuales; cada uno con SHA-256 declarado, código de salida y marcador exacto `SYPC_AUDIT_CHECK_PASS:<id>`.

Fases declaradas: `offline`, `native`, `two_node`. `mainnet` está **bloqueada explícitamente** en v0.1.

Controles implementados: versión 6.0.7 nativa, separación de referencia 4.0.5; coincidencia estricta de red, génesis, commits y ErgoTree; checks no duplicados; detección de check ausente, FAIL, BLOCKED, hash manipulado, log contradictorio, archivos con ruta peligrosa, enlaces simbólicos y FIFO; límite de bytes; hora reciente; coherencia de altura, cabecera, raíz, versión de estado, ID de nodo y rol sin minería en informes de dos nodos.

Resultados:
- `FAIL`: inconsistencia o contradicción, salida de proceso 2.
- `BLOCKED`: falta un requisito o prueba, salida 3.
- `PASS_EVIDENCE_INTEGRITY_ONLY`: **metadatos y artefactos aparentan ser coherentes**, salida 0. Este resultado **NO** significa consenso válido, transacción segura ni permiso de despliegue; `ready_for_deployment` y `ready_for_funds` son siempre `false`.

**Límite esencial:** un atacante que controla tanto el manifiesto como los logs puede falsificar hashes y marcadores. Antes de la fase real se necesita una cadena de atestación verificada de origen y cotejo con el propio resultado del validador SYPC. No abrir la red en respuesta a un PASS de metadatos.

## 4. Cómo ejecutar solo una simulación offline

No activar sobre la LAN ni cargar claves, tokens, wallet.json, secret.json, dumps, IPs de casa o logs privados en GitHub.

```bash
python3 -m unittest tests.test_sypc_swap_auditor -v
python3 tools/sypc_swap_auditor.py --policy /RUTA_PRIVADA/policy.json \
  --run /RUTA_PRIVADA/run.json --evidence-dir /RUTA_PRIVADA/artifacts
```

La política tiene exactamente estos campos:
```json
{
  "schema": "SYPC_SWAP_AUDITOR_POLICY_V1",
  "network_id": "RED_FIJADA_POR_OPERADOR",
  "genesis_id": "64 caracteres hex minúsculas",
  "core_commit": "40 caracteres hex minúsculas",
  "swap_commit": "40 caracteres hex minúsculas",
  "native_sigma_version": "6.0.7",
  "contract_sha256": "64 caracteres hex minúsculas"
}
```
Los textos de ejemplo no son valores ejecutables: no se autoriza inventar hashes o reutilizar la red equivocada.

## 5. Próxima implementación, por orden de seguridad (NO HECHA)

**G1 — Paridad nativa:** suite separada de `sigma-state 6.0.7` compilada y ejecutada contra el SYPC Core real, con comparaciones de ErgoTree, coste, firmas y rechazo de versiones no soportadas. Exigir evidencia independiente del runtime **efectivo**, no versión autodeclarada.

**G2 — Transacción completa:** construir una transacción completa de venta/compra/cancelación en cadena desechable con un input firmado por cada dueño. Verificar balance nativo y tokens, outputs y R4, fee, min-box, límites de transacción, errores y protección contra replay/doble gasto.

**G3 — Observación independiente:** dos nodos verifican el mismo bloque UTXO (no solo headers), identificación de ejecutable y génesis fijada fuera de la API, firma/atestación de origen de los reportes y watchdog de sincronización. Sin minería en el portátil.

**G4 — Seguridad de operación:** fuzzing de scripts/preflights/serialización, liveness con fees máximas y sponsor ausente, mempool, reinicio, reorgs, interrupción de red y errores de disco. Evidencia reproducible local y pruebas negativas antes de declarar GO de laboratorio.

**G5 — Mainnet, solo tras auditoría externa:** observadores en varias infraestructuras y operadores, monitores de consenso y discrepancias, eventos de precio/reserva/LP, anomalías de ejecución, hashes de releases y dependencias, umbrales de alerta; clasificación de incidente y propuesta de parche mínimo con prueba de regresión. **Nunca autorreparar cambiando consenso, carteras, claves o contratos desplegados.** La solución requiere revisión independiente, firmas y decisiones humanas.

## 6. Política de cambios

- **Parche mínimo, reversible y testeado**; evitar capas redundantes y código muerto.
- No cambiar las reglas de la moneda para hacer pasar las pruebas del DEX.
- Mantener `main`, testnet privada, nodos, carteras y minero intactos.
- No aplicar cambios de contrato a UTXOs ya creados; nuevo hash y nueva compatibilidad exigen migración explícita y pruebas de liveness.
- La detección jamás garantiza hallar toda vulnerabilidad, ni siquiera en mainnet. Reduciremos superficies ciegas con validación adversarial y revisiones periódicas.
- Conservar registro de fallos y pruebas que los reproducen, CI con commits fijados, y revisión independiente obligatoria.
