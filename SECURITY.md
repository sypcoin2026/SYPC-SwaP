# Seguridad / Security Policy

**Estado: desarrollo experimental.** No se ofrecen operaciones de exchange ni se aceptan fondos, llaves o secretos.

## Reporte responsable de vulnerabilidades

No publicar detalles explotables, claves, semillas ni material privado en issues públicos. Utilizar la función **Report a vulnerability** de GitHub, si está habilitada, para contactar a los mantenedores de forma privada. Si no estuviera disponible, no compartir exploits en público; contactar por un canal privado acordado con el mantenedor.

## Requisitos

- No enviar semillas, contraseñas o claves privadas en issues ni PRs.
- No adjuntar bases de datos de la cadena privada, direcciones internas, logs sin redactar ni volcados de wallet.
- Las pruebas deben usar fixtures sintéticos, sin datos de usuarios.
- Nunca declarar un contrato seguro por el hecho de estar escrito para Ergo o pasar pruebas unitarias.
- Prohibido habilitar cuentas de custodia, endpoints sensibles o contratos con dinero real sin auditorías y autorización.

Security reports are handled privately. No production deployment or real-funds support exists yet.
