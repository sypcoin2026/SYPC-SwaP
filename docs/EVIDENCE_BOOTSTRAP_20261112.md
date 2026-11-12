# Evidencia de arranque — 12/11/2026

**Alcance:** verificación offline de un manifiesto de referencias upstream para investigación de SYPC Swap. Ningún contrato, nodo SYPC, cartera, pool ni clave ha sido utilizado.

## Prueba ejecutada

- Entorno: Python 3.13.5, biblioteca estándar.
- Comando: `python3 -m unittest discover -s tests -v`
- Resultado: **8 tests / 8 PASS**, fallos 0, errores 0, exit code 0.
- Comando: `python3 tools/verify_sources.py`
- Resultado: **PASS — 3 referencias fijadas**, comprobación de metadatos solamente.
- Hash SHA-256 de salida de la suite (captura local): `b4c8210511094e25e619342b6ac42b59d57b3ebc19242436c36930e485077556`.

## Integridad de archivos probados y publicados

Los blobs Git de los siguientes archivos publicados en la rama `work/bootstrap-architecture-20261112` coinciden con los archivos ejecutados localmente:

| Archivo | SHA-256 del archivo probado | Git blob SHA-1 validado remoto |
| --- | --- | --- |
| `upstreams.lock.json` | `a2127bcfb3409132f16bbf54d117eaa86eeede8517e9da839903df9c86031bcf` | `f7e34fada5ee7ff5494b929ed99880b801e48a57` |
| `tools/verify_sources.py` | `1692e29232c837c60e1ad52013694e155117a614d66f7d85820617c6ad5ad655` | `b374f057e8092ac303477c370a6c28d4718f532e` |
| `tests/test_verify_sources.py` | `dac495b7fc3a7625bdc6b1daeddc3d63d28c8c10ac80c8ab5d10a0e18f2affd2` | `d7a86d97f1b9e317c8d51bc6cced19b3307d5c58` |

## Limitaciones y próximos pasos

- El programa valida que el manifiesto tenga 3 referencias con URL, hash y licencias **declaradas** correctos; **no** comprueba el contenido ni la seguridad de las licencias, los contratos o las dependencias externas.
- La opción `--local-clones` permite contrastar `HEAD` y limpieza de clones existentes **sin descargar ni modificar** nada; no ha sido probada contra esos repositorios porque no se clonaron.
- No existe evidencia de que ErgoScript, tokens nativos ni los contratos citados funcionen en SYPC.
- Ningún resultado acredita auditoría formal, DEX funcional, liquidez o disponibilidad para fondos reales.

Para repetir la prueba:
```bash
python3 tools/verify_sources.py
python3 -m unittest discover -s tests -v
```
