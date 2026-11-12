# Fuentes originales preservadas (solo consulta)

Esta carpeta conserva **8 archivos originales seleccionados** de dos proyectos Ergo, fijados a commits inmutables. **NO son contratos de SYPC** y no están enlazados a un ejecutor, cartera, nodo ni servicio. Su presencia no significa que estén auditados, compilados, desplegados ni que funcionen en la blockchain SYPC.

- `ergo-contracts/`: intercambios atómicos, órdenes limitadas, licencia de origen CC0.
- `spectrum-ergo-dex/`: contrato de pools y órdenes de swap AMM, licencia de origen CC0.
- `REFERENCES.json`: URL de repositorio, hash de commit, ruta y SHA-1 de blob Git del archivo upstream.

Los avisos `LICENSE` originales están copiados junto al código fuente. Si se toma un componente de aquí, crear una **copia adaptada en un módulo separado**, nunca modificar el original silenciosamente. Documentar cambios y revalidar scripts, dependencias, fees, identidad de red y contratos.

**IMPORTANTE:** `upstreams.lock.json` registra que ninguna biblioteca o contrato upstream está **integrado** con SYPC; estos archivos son instantáneas de investigación, no integración de producto.
