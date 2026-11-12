# Matriz de compatibilidad SYPC / DEX

**Estado: TODO PENDIENTE DE VERIFICACIÓN.** SYPC deriva de Ergo, pero no basta el origen del código para afirmar que los contratos heredados funcionarán.

| Capacidad requerida | Cómo verificarla | Estado |
| --- | --- | --- |
| Identidad de cadena/génesis y red privada | Leer parámetros de configuración y evidencias del nodo; rechazar red errónea | PENDIENTE |
| ErgoScript / Sigma validación | Compilar/evaluar contrato original en entorno local y contrato adaptado en nodo SYPC | PENDIENTE |
| eUTXO y reglas de cajas | Crear y gastar outputs encadenados, comprobar identidad de scripts y valores | PENDIENTE |
| Tokens nativos, emisión/transferencia | Transacción mínima con token de prueba sin modificar suministro nativo | PENDIENTE |
| NFT/identificador de pool | Comprobar unicidad, creación y validez de token identificador | PENDIENTE |
| Serialización y firma nativa | Verificar tx bytes, message-to-sign y claves sólo con fixtures desechables | PENDIENTE |
| Prefijos de dirección y checksum | Pruebas de direcciones de la red privada, rechazo explícito de direcciones Ergo | PENDIENTE |
| API de consulta y envío | Descubrir endpoints de lectura permitidos; envío solo con autorización de pruebas | PENDIENTE |
| Comisiones y cantidades mínimas | Probar unidades enteras, overflow y límites de valor por output | PENDIENTE |
| Reorganizaciones y mempool | Simular tx conflictivas, reorg y expiración/cancelación de órdenes | PENDIENTE |
| Compatibilidad de toolchain (Java/Scala/sbt) | Compilar dependencias fijadas offline, registrar commits, reproducibilidad | PENDIENTE |
| Windows/Linux y wallet local | Pruebas separadas para firmas nativas y experiencia segura de usuario | PENDIENTE |

## Evidencia mínima para marcar PASS

- Hash del commit y de los binarios ejecutados.
- Código de la prueba, entradas/fixtures NO secretas, entorno y comando.
- Una ejecución por suite y versión, exit code, salidas registradas y SHA-256 del informe.
- Demostrar resultado en **nodo local** y, cuando procede, corroboración independiente en segundo nodo.
- Indicar PASS o FAIL por capacidad. Nunca concluir `DEX compatible` sólo por compilar.

## Acceso a la red

La testnet SYPC actual es privada y no puede tratarse como servicio público. No exponer puertos REST, wallets, credenciales o APIs de escritura; cualquier ejecución queda diferida a una aprobación expresa del propietario.
