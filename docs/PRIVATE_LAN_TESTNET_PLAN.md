# SYPC Swap — Plan de ensayo privado en LAN (NO-GO para fondos reales)

Fecha: 2026-11-12  
Estado: **preparación verificable, sin desplegar un exchange**  
Relacionado con: [compatibilidad #2](https://github.com/sypcoin2026/SYPC-SwaP/issues/2), [transacción completa #13](https://github.com/sypcoin2026/SYPC-SwaP/issues/13).

## 1. ¿Puede probarse SYPC Swap en la cadena privada existente?

**Sí, en etapas y solo después de superar puertas técnicas.** El consenso SYPC viene de un fork de Ergo, pero los contratos y el motor Sigma portados no se han validado todavía con la transacción íntegra en la cadena actual. La actual red de dos nodos tampoco es un entorno apropiado para gastar fondos de las carteras existentes en ensayos que podrían bloquearlos.

### Etapas obligatorias

| Etapa | Entorno | Operación permitida | Evidencia y salida |
| --- | --- | --- | --- |
| 0 | Código y CI offline | Hashes de contratos, firma Sigma sintética, fuzzing, preflight | Continuar aislados de nodos reales |
| 1 | **Red privada existente, SOLO lectura** | Consultar punta íntegra, raíz, pares y diferencia entre productor/receptor | Dos snapshots con SHA-256 y coincidencia de `fullHeight`, `bestFullHeaderId` y `stateRoot` |
| 2 | **Cadena laboratorio descartable nueva** | Emitir activos de prueba, firmar con claves desechables, transacción completa y cancelación, reorg y fallos | PASS/FAIL documentados de validación de consenso |
| 3 | Red privada actual, en entorno aislado y con autorización expresa | Solo pruebas limitadas de contratos con activos específicamente destinados al ensayo, cuando existan UTXO gastables y recuperación validada | Evidencia de aceptación en productor y validador, sin operar con tesorerías |
| 4 | Mainnet pública | **PROHIBIDO** mientras estén abiertos bloqueos #13, #8, auditoría y protección de ramas | Decisión explícita tras auditoría |

**Nunca** reemplazar `genesis`, destruir datos, copiar bases vivas, reiniciar procesos activos, desbloquear carteras históricas, iniciar minería ni exponer servicios de escritura para realizar una prueba de DEX.

## 2. Red y procesos: reglas de aislamiento

- Nodo productor: minería **solo** en el equipo autorizado y **solo** si el operador arranca una sesión independiente. El ensayo DEX no inicia ni modifica GPU.
- Nodo receptor: exclusivamente validador P2P; **sin minería**.
- Ningún servicio REST ni API de cartera se expondrá fuera de `127.0.0.1`; acceder entre equipos únicamente mediante túnel SSH autenticado si se necesita una lectura remota.
- El servicio/GUI del DEX (cuando exista) escuchará inicialmente **solo loopback**. No habilitar dominio público, reverse proxy, HTTP público, `0.0.0.0` ni puertos entrantes de Internet.
- La comunicación P2P únicamente entre pares LAN permitidos. Deshabilitar descubrimiento externo y comprobar que la configuración efectiva no contiene seeds públicas.
- Comprobar firewall del host y router: sin NAT/port forwarding, sin UPnP, sin IPv6 público accidental, sin salidas de Internet para procesos de ensayo. Un test de configuración aislado **no prueba** esto.
- No confiar en que `Docker network internal` aísla automáticamente servicios enlazados fuera del contenedor; verificar reglas efectivas y tráfico. Si se usan espacios de red, probar su aislamiento con procedimientos de solo lectura.
- Utilizar datasets, credenciales y monederos **desechables**, segregados. Nunca poner `secret.json`, API keys, IPs domésticas ni snapshots privados en GitHub.
- Durante pruebas estrictamente offline, preparar previamente dependencias y artefactos revisados; una descarga desde GitHub implica tráfico hacia Internet y **no** cumpliría aislamiento estricto de la sesión.

## 3. Puerta read-only que ya podemos ejecutar cuando los nodos estén activos

Herramienta: `tools/lan_consensus_gate.py`. Python estándar, sin dependencias externas. Su código usa exclusivamente `GET http://127.0.0.1:9053/info` y `GET http://127.0.0.1:9053/peers/connected`; proxies, redirecciones y endpoints ajenos quedan prohibidos.

- En **sobremesa**, desde una copia ya descargada:  
  `python3 tools/lan_consensus_gate.py capture --role producer --out "$HOME/syp-producer-snapshot.json"`
- En **portátil**, desde su propia copia:  
  `python3 tools/lan_consensus_gate.py capture --role validator --out "$HOME/syp-validator-snapshot.json"`
- Copiar el snapshot del portátil al sobremesa mediante un canal LAN autenticado elegido por el operador; no subirlo a GitHub.  
- En sobremesa, dentro de los 5 minutos siguientes:  
  `python3 tools/lan_consensus_gate.py compare --producer "$HOME/syp-producer-snapshot.json" --validator "$HOME/syp-validator-snapshot.json"`

El guard crea snapshots nuevos con modo `0600`, nunca sobrescribe un archivo existente y entrega SHA-256. Si el nodo está parado o su API no responde, el guard falla sin iniciar nada. Si la API actual usa otros nombres de campo, el guard **falla** en lugar de adivinar o degradar su seguridad; adaptar la herramienta contra una respuesta redactada y verificada.

`PASS_READONLY_TIP_CONSISTENCY_ONLY` solo prueba que ambas respuestas locales coinciden en **punta completa y raíz de estado al instante capturado**. NO prueba que las dos redes tengan la misma génesis auténtica, que los nodos se validen de forma criptográficamente independiente, que no haya exposición al exterior, ni que un solo contrato del DEX funcione.

## 4. Requisitos de la siguiente prueba de DEX en cadena descartable

1. Identificar la versión/binario del nodo, hash del ejecutable, génesis, parámetros de protocolo, restricciones de tokens y comisiones de la **instancia desechable**.
2. Construir y firmar transacción nativa completa, no solamente verificar el ErgoScript con UTXOs sintéticos. Las dos entradas deben autenticar el mismo `messageToSign` y la salida debe conservar fondos.
3. Probar orden, ejecución, cancelación, sponsor ausente/insuficiente, doble gasto, comisiones límite, error de script, reinicio y reorganizaciones, preservando pruebas negativas.
4. Acreditar aceptación y estado después del gasto en **dos validadores**, no solo por las cabeceras o el productor.
5. Demostrar recuperabilidad incluso en mínimos de caja, renta de almacenamiento, caducidad y congestión; si no puede demostrarse, rechazar la apertura de órdenes.
6. El backend y el indexador no deben firmar ni custodiar claves. La futura wallet debe mostrar y contrastar el gasto real antes de firmar.
7. No reclamar "swap funcionando" mientras falta un caso de prueba extremo, auditoría independiente o validación del core.

## 5. Puntos abiertos y decisión

Actualmente el repo contiene preflights y scripts experimentales con tests offline; **no hay contrato desplegado, cartera con integración de firma ni exchange operativo**. La puerta read-only es un paso práctico, no un sustituto de #13.

**GO solo para la puerta de lectura local** cuando ambos nodos estén accesibles.  
**NO-GO para firma, depósito, swaps, AMM y despliegue de contratos** en la cadena existente hasta superar pruebas nativas descartables y completar los requisitos de seguridad.
