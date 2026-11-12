# Arquitectura propuesta — SYPC Swap
Fecha: 2026-11-12. **Propuesta, no implementación validada.**

## Producto: alcance por fases

**V1, intercambio nativo eUTXO:** SYPC <-> token nativo (si el núcleo demuestra compatibilidad con emisión, ErgoScript, serialización y validación de tokens); órdenes de intercambio atómico y cancelación seguras. No ERC-20, no EVM y no puentes obligatorios.

**V2, AMM:** pools de producto constante, depósitos y retiros de liquidez, ejecución off-chain abierta y verificación de toda transición on-chain. No se adopta automáticamente la implementación antigua de Spectrum: primero revisión de versión, código, licencias, dependencias y semántica para SYPC.

**V3, interoperabilidad:** proyecto separado, condicionado a auditoría del puente y su modelo de confianza. No forma parte de V1 ni V2.

## Diagrama lógico

```text
Wallet de usuario (clave privada LOCAL)
    | crea, inspecciona y firma tx
    v
Constructor local de transacciones <--- consulta -> Nodo SYPC (REST lectura local)
    | transmite tx firmada                         |
    v                                             v
Red SYPC P2P                            Indexador/observador (NO autoridad)
    |                                             |
    +--> Mineros/validadores --> Contratos eUTXO <-+
                                      |
               +----------------------+--------------------+
               |                                           |
      Órdenes atómicas / cancelación             Pool AMM y estado del pool
               |                                           |
       Ejecutores independientes (generan tx, nunca tienen claves)
```

Las órdenes deben ser **construidas y comprobadas localmente** antes de solicitar firma. Un indexador no puede sustituir validación de consenso; los datos de precios, reservas y liquidez se verifican contra UTXOs confirmados y los scripts esperados.

## Fronteras de confianza

1. **Cliente / cartera:** no exportar semillas ni claves; requiere verificación de red, cadena, contrato, destinatarios, cantidades, comisiones y salidas de cambio antes de firmar.
2. **Nodo:** fuente de observaciones, pero API remota no confiable. Validación de consenso independiente y comparación de estado/bloques antes de confiar en activos o fondos.
3. **Ejecutor:** actor sin privilegios que puede proponer transacciones pero **no** saltarse los contratos, cambiar el receptor del output ni vaciar reservas.
4. **Contrato:** única autoridad para las transiciones admisibles de UTXOs bloqueados. Ninguna clave administradora omnipotente o ruta de actualización sin límites.
5. **Índice/precio/UI:** información potencialmente manipulable; la wallet no debe firmar operaciones fuera del límite especificado por el usuario.
6. **Exploradores/terceros:** no son prueba de confirmación ni sustituyen al nodo verificador.

## Operaciones V1

- **Crear orden:** bloquea activos en un script versionado con condiciones de ejecución y condiciones de cancelación/expiración explícitas.
- **Emparejar orden:** un tercero puede construir una transacción de ejecución, pero la validación on-chain impide cantidades, destinatarios o comisiones no autorizados.
- **Cancelar/reembolsar:** demostrar que el propietario puede recuperar los activos bajo las condiciones pactadas aunque el ejecutor desaparezca o el frontend falle.
- **Esperar confirmaciones:** estados pendiente/incluido/confirmado/reorganizado, sin convertir confirmaciones probabilísticas en finalización absoluta.

## Operaciones V2

- **Crear pool:** identificador de pool no falsificable si los mecanismos de tokens/nfts están disponibles en SYPC.
- **Swap:** matemáticas enteras con límites explícitos; conservación de activos, comisiones acotadas y validación de salida mínima.
- **Añadir/quitar liquidez:** reglas de proporcionalidad/participaciones, redondeo, restricciones de reservas y cuotas bien definidas.
- **Ejecutores:** diseño sin operador único y con prueba de progreso/cancelación ante denegación de servicio.

## Decisiones que permanecen ABIERTAS

- ¿ErgoScript, tokens nativos y operaciones con cajas registradas siguen habilitados exactamente igual en los binarios SYPC usados?
- ¿Qué identificadores de red/génesis, prefijos de dirección y reglas de transacción/versionado están activos?
- ¿Qué contratos upstream aceptamos o adaptamos (sha fijo, test reproducible, revisión de licencia)?
- Política de comisiones, tolerancia de deslizamiento, expiración y confirmaciones.
- Implementación de firma: reutilización de librerías de cartera compatibles en lugar de crear criptografía propia.

**Prohibiciones:** alterar consenso, minar, usar carteras privadas, iniciar una DEX con fondos reales o exponer APIs de escritura para probar este diseño.
