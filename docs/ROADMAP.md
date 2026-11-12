# Hoja de ruta y trabajo inmediato

## P0 — Alcance y licencias [documentado, sin integración]

- [x] Repositorio público separado del núcleo.
- [x] Catálogo de referencias Ergo y Spectrum (commits fijos, licencias).
- [x] Propuesta de arquitectura nativa sin puentes y matriz de compatibilidad.
- [x] Ocho archivos upstream preservados con sus licencias e integridad comprobada.
- [x] Modelo aritmético AMM offline y comprobador de snapshots: 25 tests sintéticos/aritméticos PASS.
- [x] Gate experimental de intenciones offline, tests adversariales y CI de solo lectura (PR #5 en borrador).
- [ ] Configurar proteccion de rama con checks requeridos (issue #6).
- [ ] Revisión del código/contratos específicos y de sus dependencias.
- [ ] Decidir licencia propia del proyecto antes de publicar código nuevo reutilizable.

## P1 — Compatibilidad núcleo SYPC [pendiente]

- [ ] Revisar ErgoScript, eUTXO y transacciones reales de la rama SYPC que se esté ejecutando, **sin tocar consenso**.
- [ ] Verificar emisión y transferencia de tokens nativos de prueba.
- [ ] Validar prefijos SYPC, red/génesis, serialización, fees, scripts.
- [ ] Registrar resultados con hashes, pruebas y evidencias independientes.

## P1.5 — Seguridad del intercambio atómico [investigación avanzada]

- [x] Conservar y estudiar los predicados originales de compraventa/cancelación de Ergo en el laboratorio offline.
- [x] Reproducir la compilación de contratos candidatos con Sigma 4.0.5 y **aislar el estado del compilador**: 4 tests Scala PASS (no demuestra consenso SYPC).
- [x] Desarrollar un modelo de preflight de cancelación con una entrada, retorno exacto de activos y comisión acotada; 134 tests Python PASS en CI.
- [ ] Revalidar hashes de ErgoTree entre procesos, plataformas y versiones antes de publicar cualquier contrato.
- [ ] Decidir si la cancelación debe imponer devolución on-chain incluso con firma de propietario, en lugar de confiar únicamente en la cartera.
- [ ] Compilar y ejecutar los contratos portados en nodo SYPC de laboratorio independiente.
- [ ] Auditoría de claves, cambios de UTXO, tokens, fees y reorgs de la transacción **completa**, no sólo de un predicado.

- [x] Audit de workflows y permisos de GitHub agregado a CI, con **145/145 tests PASS** (Python 3.12 y 3.13).
- [ ] **Bloqueo P0:** habilitar ruleset de `main` con CI obligatorio y revisión humana (issue #6).

- [x] 12 tests reales del intérprete Sigma 4.0.5 en Ubuntu 22.04 y 24.04, compra y venta con UTXOs sintéticos, con huellas SHA-256 idénticas entre ambos entornos.
- [x] Huellas de los dos ErgoTrees fijadas como aserciones de regresión en el CI de investigación.
- [ ] Interpretación con el binario y reglas de consenso **SYPC**; todavía no demostrada.
- [ ] Validez de la transacción completa, comisiones, conservación, doble gasto, cancelación con firma y recuperación ante reorganización de bloques.

## P1.6 — Cancelación verificable y recuperabilidad [solo laboratorio]

- [x] Probar con firmas Sigma la rama heredada de cancelación; riesgo de destinatarios no garantizados confirmado (`8/8` pruebas).
- [x] Primer contrato de devolución exacta, comisión acotada y firma del propietario: `17/17` PASS en dos Ubuntu.
- [x] Variante con UTXO patrocinadora nativa del mismo propietario y selección de inputs sin indexado opcional: `27/27` PASS.
- [x] Firma y verificación de **ambas** entradas sobre `messageToSign` idéntico en transacción sintética: `29/29` PASS en dos Ubuntu.
- [ ] **P0**: demostrar validez global de una tx SYPC, firmas múltiples, costes, tokens reales y reorgs mediante nodos validadores independientes.
- [ ] **P0**: demostrar que ningún estado permitido impide cancelar/reembolsar por falta de native-value mínimo y que no se bloquean fondos.
- [ ] **P0**: auditoría externa, pruebas formales y protección de `main`; nada de despliegue público todavía.

## P2 — Intercambio atómico [pendiente]

- [ ] Seleccionar contrato origen y preparar port aislado con licencia/procedencia.
- [ ] Compilar, ejecutar suite original, port y suite de invariantes.
- [ ] Crear prueba privada de orden/cancelación/ejecución sin fondos reales.
- [ ] Revisar seguridad de un ejecutor sin custodia, estados de expiración.

## P3 — AMM [pendiente]

- [ ] Auditar Spectrum AMM y dependencias de pool/NFT/LP.
- [ ] Implementar/adaptar contratos tras P1/P2 y probar propiedades.
- [ ] Ejecutores abiertos, autenticación de índices, recuperación de órdenes, tests adversariales.

## P4 — Integración [pendiente]

- [ ] Wallet local con firma y visualización verificada de transacciones.
- [ ] UI de mercado y liquidez sin custodio.
- [ ] Soporte Linux/Windows, instalaciones verificables, documentación bilingüe.

## P5 — Pre-mainnet [bloqueado]

- [ ] Auditoría independiente, revisión de cadena y liquidez, modelo económico, requisitos legales.
- [ ] Sólo activar mediante decisión expresa y con evidencia.

**No hay fecha de mainnet ni DEX activo.** La seguridad precede a la apariencia de la interfaz.
