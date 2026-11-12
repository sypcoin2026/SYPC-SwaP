# Modelo de amenazas — SYPC Swap

**Documento de ingeniería, no garantía de seguridad.** Riesgo económico elevado. No se aceptan depósitos ni fondos reales.

## Activos a proteger

- SYPC y tokens bloqueados en órdenes y pools.
- Propiedad de LP, valor de reservas, asignaciones y reembolsos.
- Semillas, claves privadas, transacciones firmadas y privacidad de usuario.
- Correctitud del precio mostrado, UTXOs y estado confirmado por nodo.

## Agentes y vectores

| Vector | Consecuencia | Control propuesto |
| --- | --- | --- |
| Ejecutor malicioso | Robo, censura, manipulación de outputs | Scripts que verifican cada transición, ejecutores sin permisos, cancelaciones |
| Frontend / indexador comprometido | Firma engañosa, sustitución de token | Verificación local de tx, red, script hash, cantidades, destino, comisiones y cambio |
| Reorg / doble gasto / mempool | Operaciones reversibles o expiradas | Estados de confirmación, respuesta a reorganización, no confiar en mempool |
| Pool falso / activo suplantado | Pérdida de fondos | Identidad de contratos/tokens fijados por hash, mostrar identificadores completos |
| Manipulación de precio / MEV | Extracción económica, slippage | Cantidad mínima recibida, plazo de validez, precio límite, no revelar órdenes sensibles innecesariamente |
| Desbordamiento o redondeo | Pérdida / extracción por polvo | Aritmética entera, rangos, cotas, propiedades y tests extremos |
| Ataque de donación/primer depósito | Precios/participaciones incorrectos | Inicialización verificada y cantidades mínimas de LP |
| Claves de administración | Extracción de pools o cambios unilaterales | Evitar poderes de custodia; si hubiera gobierno, restricciones y revisión específica |
| Clave privada expuesta / supply chain | Robo directo | Firma local, dependencias fijadas, builds reproducibles, auditoría, no telemetry secretos |
| Ejecutores desaparecidos | Bloqueo indefinido de fondos | Cancelación/expiración/reembolso accesibles al usuario |
| Fallo criptográfico / cadena propia | Invalidación de supuestos de Ergo | Pruebas de compatibilidad en núcleo SYPC; no alterar consenso en este repo |

## Invariantes obligatorios

1. Ningún ejecutor o administrador puede transferir fondos de una orden/pool sin cumplir el script y sus destinatarios/condiciones.
2. Conservación de activos: entradas = salidas + comisiones explícitamente admitidas por las reglas de la cadena. No acuñación implícita de SYPC.
3. Para cada swap, la cantidad recibida por el propietario es `>= minAmountOut` o la transacción falla.
4. La cancelación legítima devuelve valor al propietario bajo condiciones comprobadas; documentar pérdidas máximas en comisiones.
5. Identidad de red, cadena, contrato y token visible y vinculada a la firma. Nunca interpretar una dirección Ergo como SYPC.
6. No salida de claves privadas ni envío a servidores de la firma; el frontend nunca custodia fondos.
7. La retirada de LP no puede superar la fracción de reservas autorizada por el contrato.
8. El pool no acepta operaciones que ignoren las reglas de transición, comisiones, reservas o token identificador.
9. Reorgs, replays, operaciones duplicadas, expiración y reintentos son estados definidos y probados.
10. Ninguna conclusión de seguridad se basa únicamente en tests unitarios o adaptación de código histórico.

## Estrategia de verificación

- Modelo de estados eUTXO de órdenes/pools; probar propiedad por propiedad.
- Unit tests, property-based fuzzing, simulaciones de red y pruebas negativas de gasto.
- Pruebas con datos adversariales: overflow, cero, máximo entero, token duplicado, fee negativa, precio obsoleto, indexador falsificado, reorg y UTXOs conflictivos.
- Revisión de contratos fuera de la UI; revisión separada de ejecutor, backend, wallets y dependencias.
- Auditoría independiente antes de mainnet o fondos reales.
- Proceso de divulgación responsable definido en la raíz del repositorio.

## Gate de seguridad previo al lanzamiento

No existe fecha de lanzamiento aprobada. Para habilitar dinero real hacen falta **todas** las pruebas de compatibilidad, red suficientemente segura/descentralizada, contrato y build reproducibles, auditoría externa, divulgación de riesgos, y autorización explícita. Si falla una condición, mantener software en modo privado/experimental.
