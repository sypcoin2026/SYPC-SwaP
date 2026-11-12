# SYPC Swap

**DEX nativo en investigación para la blockchain SYPCoin (SYPC).**  
**Estado: diseño experimental. No hay contratos desplegados, intercambios disponibles ni auditoría final. No utilizar fondos reales.**

SYPC Swap es un proyecto independiente para estudiar, adaptar y reforzar tecnologías abiertas del ecosistema **Ergo/eUTXO**, sin reinventar innecesariamente un exchange descentralizado ni modificar a ciegas el consenso de SYPCoin.

## Objetivo

- **Primera fase:** intercambios atómicos *sin custodia* de SYPC y activos nativos, sujetos a que la red SYPC admita y valide los contratos y tokens correspondientes.
- **Segunda fase:** pools de liquidez AMM, órdenes, ejecutores independientes y una interfaz web/desktop de firma local.
- **Tercera fase:** estudiar interoperabilidad externa (BTC, ETH y otros) **aparte** del DEX nativo, con evaluación específica de riesgos de puentes.
- No se crea otra moneda, ni una reserva de fundador, ni se alteran los **28 millones SYPC** previstos para el núcleo de SYPCoin. Esta cifra procede del diseño económico del proyecto y no acredita activación del consenso.

## Principios

1. **No custodial:** no se recopilan semillas ni claves privadas, nunca se firma en servidor.
2. **Separación:** este repositorio no cambia, despliega ni controla `sypcoin-core`, los nodos o la minería.
3. **Seguridad demostrable:** especificación de invariantes, pruebas adversariales, análisis estático/formal donde proceda y auditoría externa previa a dinero real.
4. **Reutilización comprobada:** aprovechar código abierto verificado por revisión de licencia, procedencia, dependencias y semántica; nunca presumir que un contrato heredado está auditado para SYPC.
5. **Sin puentes en V1:** los intercambios iniciales serán entre activos en la misma blockchain; cualquier representación externa tendrá su propio proyecto y modelo de amenazas.
6. **Publicación honesta:** compilación, test offline, ejecución en testnet privada y seguridad auditada son niveles de evidencia diferentes.

## Referencias técnicas (todavía NO integradas)

| Referencia | Interés | Estado |
| --- | --- | --- |
| [Spectrum Finance / ergo-dex](https://github.com/spectrum-finance/ergo-dex) | AMM, pools, órdenes y ejecutores off-chain | En estudio; licencia CC0-1.0 del repositorio |
| [Ergo Contracts](https://github.com/ergoplatform/ergo-contracts) | Intercambio de activos y propiedades con verificación formal | En estudio; licencia CC0-1.0 del repositorio |
| [Ergo / ergo-dex](https://github.com/ergoplatform/ergo-dex) | DEX de órdenes y arquitectura eUTXO | En estudio; licencia MIT del repositorio |

La compatibilidad de esos proyectos con SYPC **no está demostrada** y requiere validaciones de compatibilidad, pruebas nativas y revisión de código y licencias por componente. Se han preservado ocho archivos de código y licencias originales, sin modificaciones, en [`third_party/`](third_party/README.md). Son referencias de investigación: **no están integradas con SYPC ni desplegadas**.

## Pruebas offline (no comprueban contratos)

```bash
python3 tools/verify_sources.py
python3 tools/verify_vendored.py
python3 -m unittest discover -s tests -v
```

El proyecto incluye un **modelo matemático de AMM**, no un exchange ejecutable ni una cotización de mercado. La [evidencia de fase 1](docs/EVIDENCE_PHASE1_20261112.md) distingue los niveles de prueba.

## Seguridad preventiva — fase 2

Se han desarrollado [validaciones offline **fail-closed**](docs/SECURITY_GATES_PHASE2.md) que rechazan cambios de red, pool, activos, destinatario, UTXO, vencimiento y comisiones. Un [workflow de seguridad](.github/workflows/security-offline.yml) comprueba los snapshots originales y ejecuta pruebas negativas en Python 3.12/3.13.

**Importante:** no es un exchange funcional. Ninguna firma ni contrato de SYPC se ha ejecutado; los gates son defensa en profundidad e **insuficientes para fondos reales**. La integración se revisa en el [PR de seguridad](https://github.com/sypcoin2026/SYPC-SwaP/pull/5).

## Hoja de ruta

- **Fase 0 — documentación y pruebas de compatibilidad:** modelo de amenazas, invariantes, catálogo de dependencias y prueba de ErgoScript/tokens de la red privada.
- **Fase 1 — intercambio atómico:** seleccionar/adaptar contratos existentes y probar emisión, firma, ejecución, cancelación, expiración y reorganizaciones.
- **Fase 2 — AMM experimental:** adaptar pools y ejecutores existentes, con simulaciones, tests de invariantes y controles de precio y deslizamiento.
- **Fase 3 — interfaz y pruebas de integración:** wallet no custodial, visualización verificable, pruebas multinodo y fallo seguro.
- **Fase 4 — preparación para auditoría:** revisión externa, reproducibilidad de compilaciones, divulgación responsable y decisión explícita sobre lanzamiento.

## Seguridad y trabajo

Los contratos **adaptados a SYPC**, el backend ejecutor, la UI y los endpoints públicos todavía **no existen** en este proyecto. No se aceptan depósitos, no hay pools ni tokens SYPC Swap.

Antes de integrar código ajeno, revisar [documentación de procedencia](docs/UPSTREAM.md), [arquitectura](docs/ARCHITECTURE.md), [compatibilidad](docs/COMPATIBILITY.md) y [modelo de amenazas](docs/SECURITY_MODEL.md) y la [revisión estática](docs/STATIC_COMPATIBILITY_REVIEW_20261112.md).

**Nunca publicar** wallet data, claves, frases semilla, credenciales, volcados de bases de datos, IPs internas, ficheros .env, logs privados ni datos de red experimental.

**English:** SYPC Swap is an experimental, native non-custodial DEX research project for SYPCoin's eUTXO-based blockchain. There are no deployed contracts, live trading facilities, audited releases or real-fund support. Upstream Ergo ecosystem projects are being evaluated, not yet integrated.

---
*Proyecto experimental del ecosistema SYPCoin. No es un servicio financiero activo ni una promesa de cotización o liquidez.*
