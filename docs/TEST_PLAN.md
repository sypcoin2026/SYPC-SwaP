# Plan de validación reproducible

**No ejecutar nodos ni minería desde este repositorio sin autorización.** El desarrollo comienza por lectura, contratos offline y pruebas de red aislada.

## T0: prueba de procedencia

- Verificar licencia del componente exacto, commit fijo y hash de archivo.
- Compilar upstream contra dependencias fijadas. Registrar problemas conocidos y versiones.
- Comparar comportamiento contra el código portado. No confundir mismo resultado con misma seguridad.

## T1: compatibilidad de ejecución

- Rechazo de direcciones de red errónea y prefijos heredados.
- Verificar que script y serialización de contrato coinciden con interpretación del nodo SYPC.
- Crear/transferir/gastar token de prueba sólo después de validar que el núcleo lo permite.

## T2: órdenes nativas

- Crear/cancelar/expirar/ejecutar con una cartera de pruebas desechable.
- Ejecutar duplicado, coste superior al autorizado, salida mal dirigida, token falso, signature inválida, UTXO gastado, fallo de ejecutor.
- Nunca necesitar claves del usuario en un ejecutor ni en el navegador de terceros.

## T3: pools AMM

- Reservas vacías, depósitos iniciales, retiros, cambio de precio, swaps sucesivos.
- Testear matemáticas enteras con redondeos a ambos lados y propiedades de no extracción.
- Imposibilidad de redirigir tasas/comisiones no autorizadas.
- Control de slippage, cambios de reservas y tx obsoletas.
- Concurrencia: dos ejecutores compitiendo por el mismo UTXO, reintentos y rollback.

## T4: red y UX

- Dos nodos validadores independientes, mismo `stateRoot` y `bestFullHeaderId` cuando aplique.
- Reorg, pérdida de conectividad, mempool saturado, RPC mentiroso, nodos con lag.
- Plataforma Linux y Windows con fixture/simulación antes de firma real.
- Sólo API de lectura expuesta localmente; no usar carteras reales.

## Criterio PASS

- Un resultado PASS exige entradas, versión/commit, comando exacto, exit code, log redactado, SHA-256 de evidencia, y ausencia de desvíos de red.
- Documento explícito que distinga unit test de demostración con nodo SYPC real.
- La suite local exitosa **no** constituye auditoría ni autorización para operar fondos reales.
