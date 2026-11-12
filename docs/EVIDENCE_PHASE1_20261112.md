# Evidencia: SYPC Swap · 12-11-2026

**Alcance:** fuentes originales preservadas, revisión estática del núcleo y modelos offline. Sin contratos adaptados, sin trading, sin uso de fondos, sin pruebas sobre nodos reales.

## Procedencia

- Ocho archivos originales de Ergo Contracts y Spectrum preservados en `third_party/` con sus licencias y commits completos. Los 8 hashes Git de las copias publicados coinciden con los originales recuperados del repositorio de origen.
- Revisión estática del núcleo SYPC: `docs/STATIC_COMPATIBILITY_REVIEW_20261112.md`.
- No se ha comprobado compatibilidad en ejecución.

## Pruebas efectivamente ejecutadas

- Python 3.13.5, librería estándar, entorno aislado sin red.
- Comando: `python3 -m unittest discover -s tests -v`.
- Resultado: **25/25 PASS**, 0 errores, 0 fallos, exit code 0.
- 18 casos de matemática AMM (incluidos 4000 ejemplos pseudoaleatorios deterministas) + 7 casos sintéticos del verificador de referencias.
- SHA-256 de la salida capturada: `56a18f8dc6ce05a27d798002fe028200435a864922b8de3a53d276f8871f6453`.
- Se comprobó que los blobs de los cuatro archivos de código/test publicados son idénticos a los probados:
  - `sypc_swap/offline_amm.py`: `e8808c02fdedb5ad860ed756dd7dd110b652895e`
  - `tests/test_offline_amm.py`: `47cd2d8c88371178442a3678814ecb4e19f52fca`
  - `tools/verify_vendored.py`: `a2595a9b1752f14c49f68c5148a6dff5c853e9ca`
  - `tests/test_verify_vendored.py`: `209967b105853f22103eb5a84d9c6c5faa758429`

## Límites

- Las pruebas son solo de aritmética y de fixtures sintéticos; no son tests de ErgoScript ni validación de transacciones.
- Las ocho copias originales fueron cotejadas remotamente; `tools/verify_vendored.py` aún no se ha ejecutado localmente contra un clon íntegro del repositorio (su lógica sí fue probada con fixtures).
- No se ejecutaron suites Scala originales: `sbt` no estaba instalado en el entorno de pruebas.
- El multiplicador de comisión 997/1000 **es un dato de prueba, no una tarifa aprobada**.
- No modificar consenso, carteras, nodos ni GPU sin instrucciones explícitas.

## Repetición en un clon limpio

```bash
python3 tools/verify_sources.py
python3 tools/verify_vendored.py
python3 -m unittest discover -s tests -v
```

Mantener PR en borrador hasta revisión técnica y prueba de contratos con la red privada.
