# Privacidad al contribuir

Para informar de compatibilidad basta con compartir:

- distribución y escritorio, si deseas hacerlo;
- identificador compartido vendor/product del control HID;
- si aparece la señal conocida del botón;
- si se seleccionó el perfil esperado y si el LED respondió;
- el mensaje de error pertinente, sin el encabezado del registro.

El modelo comercial es opcional. No compartas números de serie o SNID,
UUID, MAC, direcciones de red, nombre de equipo, rutas de tu carpeta personal,
nombre de usuario, correos, tokens ni salidas completas de DMI, ACPI o registros.
No adjuntes tablas de firmware ni capturas de tu escritorio.

El README incluye únicamente el modelo comercial, la distribución, el
escritorio y el kernel del entorno probado, además del controlador y los
identificadores compartidos del protocolo. Son referencias de compatibilidad;
no se publican identificadores únicos de la unidad ni datos personales.

`--check` y `--listen` imprimen sólo información limitada del protocolo conocido;
no exportan los datos de identificación de la unidad. Revisa de todas formas
cualquier texto antes de compartirlo.

El repositorio se preparó desde una carpeta nueva: no contiene el historial de
trabajo, las pruebas originales ni las copias de configuración de la máquina.
La autoría de Git es genérica. Si añades commits, revisa el nombre y correo que
Git vaya a grabar antes de publicarlos. Publicar desde tu cuenta de GitHub hará
visible esa cuenta como propietaria del repositorio; esto es independiente de
los datos locales del equipo.
