# SYPC Swap — Security gates phase 2

> Fecha: 12/11/2026. Investigacion experimental, **SIN contratos SYPC compilados o desplegados**. No autoriza dinero real.

## Contrato de seguridad del prototipo

**Deny by default:** la funcion `sypc_swap/trade_preflight.py::preflight_trade` rechaza cualquier intencion incompleta o incoherente. No genera, firma ni transmite transacciones.

Para una intencion aceptada se exigen simultaneamente:

- Identidad de genesis fijada por politica local y contexto externo supuestamente verificado.
- Hash de script, NFT del pool y **par de activos** fijados en una allowlist local; no se aceptan tokens cambiados por un indexador.
- ID de caja UTXO del pool coincidente con el contexto externo independiente, ademas de la intencion y el snapshot.
- Bloque/altura del snapshot e intencion exactamente iguales a la punta indicada en el contexto. No se aceptan cotizaciones antiguas.
- Hash de script destinatario igual al previsto por la politica local; no se confia en un texto de direccion Ergo/SYPC.
- Cantidades enteras positivas, acotadas a 64 bits con signo; matematicas intermedias en Python de precision arbitraria.
- `minimum_out` coherente con el producto constante, el redondeo hacia abajo y los limites de deslizamiento.
- Comision de minero dentro del maximo local y una altura de expiracion dentro de la ventana autorizada.
- Hash SHA-256 reproducible de la intencion para facilitar comparaciones en pruebas, **NO firma ni autenticacion**.

El modelo `SYPC_NATIVE` es un marcador de laboratorio, **NO** un identificador de consenso.

## CI de solo lectura

El workflow `.github/workflows/security-offline.yml` se ejecuta para ramas de trabajo y PRs, con permisos `contents: read`, acciones fijadas a commits y Python 3.12 y 3.13. Exige:

1. Metadatos correctos de referencias originales, sin descarga automatica.
2. Integridad byte a byte de archivos copiados de Ergo y Spectrum contra los hashes Git fijados.
3. Control AST sobre el paquete offline `sypc_swap/` para detectar importaciones de red, subprocess o llamadas dinamicas habituales.
4. Todos los tests unitarios offline, incluidos los casos adversariales.

El AST es una **alarma de mantenimiento**, no un sandbox ni una prueba de ausencia de malware. Tampoco constituye una auditoria criptografica.

## Riesgos bloqueantes que siguen abiertos

| Prioridad | Riesgo | Requisito antes de usar fondos |
| --- | --- | --- |
| P0 | Contexto `VerifiedContext` falsificable | Obtener genesis, tip y UTXO de un nodo verificado; no confiar en campos declarados por la UI |
| P0 | Contratos originales no ejecutados en SYPC | Reproducir compilacion Scala/ErgoScript, test original y port separado con validacion nativa |
| P0 | Wallet no vinculada al hash de la intencion | Comprobar los outputs reales de la transaccion y firmar localmente solo tras verificacion de usuario |
| P0 | Comprobacion de validez UTXO incompleta | Demostrar no gastado, altura, indices, identidad de pool y resistencia a reorganizaciones |
| P0 | Liquidez/activos suplantados | Verificar emision y transferencias de tokens nativos, registro de pool e identidad de los scripts |
| P1 | Limites de VM y redondeo distintos de Python | Ejecutar pruebas equivalentes en entorno Sigma/Ergo y probar overflow/dust/costes |
| P1 | Revision de terceros pendiente | Auditoria independiente de contrato, wallet, ejecutor y dependencias |
| P1 | GitHub no requiere aun el check para fusionar | Configurar branch protection/ruleset con checks obligatorios y revisiones humanas |

## Resultado comprobado

- Fase 2 local: 34/34 pruebas PASS (23 casos de preflight + 9 de AST y 2 adicionales de pool/activos), Python 3.13.5, sin nodos ni cartera.
- Workflow: [ejecucion GitHub #43229178689](https://github.com/sypcoin2026/SYPC-SwaP/actions/runs/43229178689). Jobs Python 3.12 y 3.13 **success**. En la version 3.13 se registraron **67 tests PASS**; los checks de metadatos, archivos y AST tambien PASS.

## Niveles de seguridad (no intercambiables)

`unit tests offline` != `contrato compilado` != `testnet privada` != `auditoria independiente` != `apto para fondos reales`.

**Decision:** seguir desarrollando en rama aislada y PR en borrador. No cambiar consenso ni tocar mineria/nodos/carteras.
