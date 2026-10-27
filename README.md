# Acer Mode Button for Linux

Un servicio pequeño para usar el botón físico de modos de energía de algunos
portátiles Acer con Linux. Escucha un mensaje HID específico y cambia entre los
perfiles que ofrece `powerprofilesctl`. En KDE Plasma muestra el indicador
nativo de perfil.

**Alcance limitado:** se verificó una implementación local con Fedora y KDE.
No hay garantía de compatibilidad con toda la familia Nitro o Predator. Se
publica una ficha técnica mínima de compatibilidad, sin datos que identifiquen
la unidad concreta donde se hicieron las pruebas.

## Compatibilidad

Entorno de las pruebas físicas de la implementación original:

| Dato | Valor |
| --- | --- |
| Modelo | Acer Nitro ANV16-42 |
| Distribución | Fedora Linux 44 |
| Escritorio | KDE Plasma |
| Kernel | `7.2.12-200.fc44.x86_64` |
| Controlador de plataforma | `acer_wmi`, incluido en Fedora |

Esta ficha documenta el entorno probado; no exige usar esa misma versión de
kernel. No se incluyen el número de serie, la versión de BIOS ni otros datos
de identificación de la unidad.

La configuración incluida espera:

| Elemento | Valor |
| --- | --- |
| Interfaz | I2C HID, bus `0018` |
| Vendor/product | `1025:174B` |
| Mensaje exacto del botón | `04 85 ff` |
| Gestión de energía | `powerprofilesctl` con `power-saver`, `balanced` y `performance` |
| Inicio de servicios | systemd y udev |
| Aviso en pantalla | KDE Plasma, opcional; sesión local activa en `seat0` |

Encontrar el mismo identificador HID **no demuestra** que el botón emita el
mismo mensaje. Antes de instalar, verifica las dos cosas:

```bash
python3 src/acer_mode_button.py --check
sudo python3 -I src/acer_mode_button.py --listen
```

El segundo comando abre únicamente el control HID identificado, en lectura.
Pulsa el botón: debe imprimir `boton_detectado` y `04 85 ff`. Termina con
`Ctrl+C`. En este modo no cambia el perfil ni imprime otros informes HID.

Si el control no aparece, hay varias coincidencias, no sale el mensaje, el
botón ya funciona de forma nativa o ya lo gestiona otra aplicación, **no
instales un segundo gestor del mismo botón**. Un cambio de protocolo requiere
adaptación y una prueba propia; no amplíes la regla a todos los dispositivos HID.

## Comportamiento

| Alimentación | Ciclo |
| --- | --- |
| Cargador conectado | Ahorro → Equilibrado → Rendimiento → Ahorro |
| Batería | Ahorro ↔ Equilibrado |

El perfil seleccionado aparece también en la barra de energía del escritorio.
En el hardware probado, el firmware cambia el color del LED al cambiar el perfil.
Este programa no controla directamente el LED, los ventiladores ni los registros
del controlador integrado. Los perfiles son los de Linux: no se implementa un
selector independiente de todos los modos de NitroSense de Windows.

## Instalación

Requisitos: Python 3, systemd, udev y una implementación compatible de
`powerprofilesctl`. En Fedora, los paquetes utilizados son `python3`,
`systemd-udev` y `power-profiles-daemon`. Verifica primero:

```bash
powerprofilesctl list
python3 src/acer_mode_button.py --check
```

Tras confirmar el mensaje con `--listen`, desde la carpeta del repositorio:

```bash
sudo python3 -I manage.py install
systemctl status acer-nitro-mode.service
```

El instalador comprueba las dependencias, rechaza archivos ya existentes y no
modifica el controlador Acer ni parámetros de arranque. No instala módulos,
paquetes, repositorios ni DKMS. Si la instalación falla, retira los archivos
que acababa de crear. Conserva un registro de huellas para la desinstalación.

Archivos administrados:

```text
/usr/local/libexec/acer-nitro-mode.py
/etc/systemd/system/acer-nitro-mode.service
/etc/udev/rules.d/90-acer-nitro-mode.rules
/var/lib/acer-nitro-mode-public/install.json
```

No ejecutes dos copias simultáneas del servicio: una pulsación podría avanzar
más de un perfil. La copia pública es una adaptación de la implementación
probada; el instalador no sustituye instalaciones anteriores automáticamente.

## Actualizaciones de kernel y reconexión

La aplicación se ejecuta en espacio de usuario y no depende de una versión de
kernel ni de un módulo externo compilado. udev crea `/dev/acer-nitro-mode`
usando la identidad compartida del control. systemd espera a que exista el
dispositivo, detiene el servicio al retirarlo y lo inicia de nuevo al aparecer.
El permiso de lectura se vuelve a resolver en cada arranque del servicio.

El programa busca la identidad HID en sysfs; no presupone `hidraw0`. Los errores
del proceso se reintentan cada cinco segundos, sin agotar una cuota de intentos.
Esto cubre cambios normales de enumeración y recuperación. No garantiza una
futura compatibilidad ante cambios incompatibles del firmware o de Linux.

## Comprobaciones y límites

En la implementación original se verificaron físicamente el botón, el ciclo de
perfiles, el LED del equipo, la desconexión/reconexión de la interfaz de control
y la recuperación tras una terminación forzada del proceso. La restricción de
batería y el reconocimiento con distintas numeraciones se comprobaron con
pruebas de lógica. No se probó arrancar una versión de kernel diferente.

La adaptación pública añade detección dinámica de la sesión de KDE y modos
`--check`/`--listen`. Las pruebas automatizadas usan simulaciones para estas
rutas; no equivalen a una prueba física en otro portátil. El modo `--check`
tampoco demuestra que el botón funcione.

```bash
python3 -m unittest discover -s tests -v
systemd-analyze verify systemd/acer-nitro-mode.service
udevadm verify udev/90-acer-nitro-mode.rules
```

Para consultar errores locales:

```bash
journalctl -u acer-nitro-mode.service -b --no-pager
```

No publiques esa salida completa: el envoltorio del registro puede contener
nombre de equipo, fechas y otra información local. Comparte únicamente el
mensaje pertinente, redactado según [PRIVACY.md](PRIVACY.md).

## Detener o desinstalar

```bash
sudo systemctl stop acer-nitro-mode.service
sudo python3 -I manage.py uninstall
```

La desinstalación conserva el perfil elegido y se niega a borrar archivos cuyo
contenido difiera del registro de instalación. En ese caso, revisa tus cambios
antes de retirarlos manualmente.

## Seguridad y privacidad

El servicio requiere administración para leer el nodo HID protegido y llamar
al gestor de perfiles. Tiene acceso de dispositivo limitado a lectura del
control Acer, no lee el teclado y carece de capacidades adicionales. El sistema
de archivos está protegido contra escritura dentro del servicio.

No recopila telemetría ni ejecuta solicitudes de red. No incluye capturas,
tablas ACPI, números de serie, UUID, MAC, datos de BIOS, rutas personales,
nombres de usuario ni registros reales. Los archivos Git usan autoría genérica
y no incluyen el correo personal de la persona que prepara el repositorio.

## Referencias y reconocimiento

- [Predator Sense for Linux: Physical mode-switch key](https://github.com/cleyton1986/predator-sense#physical-mode-switch-key): documentación del mensaje HID observado también aquí. No se incorporó código de ese proyecto.
- [Linux: interfaz hidraw](https://www.kernel.org/doc/html/latest/hid/hidraw.html).
- [systemd: unidades de dispositivo y udev](https://www.freedesktop.org/software/systemd/man/latest/systemd.device.html).
- [systemd: dependencias de unidades](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html).

Proyecto independiente, sin afiliación con Acer. Licencia [MIT](LICENSE).
