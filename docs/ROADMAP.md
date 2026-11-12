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
