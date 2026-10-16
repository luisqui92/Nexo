# Nexo · Inmobiliaria

Primera versión funcional del sistema inmobiliario basado en la idea de Vitalis:
conversación → hoja revisable → expediente → siguiente acción.

## Preparar la presentación

Abrir **`presentar.py`** en Pydroid o ejecutar `python presentar.py` en una
computadora. Prepara un espacio aislado en `data_presentacion/`, con gerencia,
dos asesores, carteras asignadas y datos ficticios. No reemplaza `data/`.
La consola muestra los accesos de la demo. En el panel central está
**Preparar presentación**, con comprobaciones y acceso a ocho diapositivas.
El guion completo está en **GUIA-PRESENTACION.md**.

## Ejecutar

Requiere Python 3.10 o posterior. No necesita instalar paquetes.

```sh
python server.py
```

Abrir **http://127.0.0.1:8080**. En Windows también se puede usar `py server.py`.

La base SQLite, las cuentas y los archivos se guardan en `data/`. Al abrir por
primera vez, crear el usuario y contraseña del **administrador** (mínimo 10
caracteres). Esto abre el panel central. Allí se ofrece **Explorar con una demo** para cargar datos ficticios si el espacio está vacío.
También puede comenzar directamente con **Nuevo cliente** y **Agregar inmueble**.
La demo nunca reemplaza datos ya registrados.

## Probar desde Android con Pydroid 3

1. Descomprimir el proyecto conservando todas sus carpetas y archivos juntos.
2. En Pydroid 3, abrir `server.py` desde esa carpeta y pulsar Ejecutar.
3. Mantener el proceso ejecutándose, abrir Chrome y visitar
   `http://127.0.0.1:8080`.
4. Si Android suspende el servidor al cambiar de aplicación, abrir Ajustes →
   Aplicaciones → Pydroid 3 → Batería y seleccionar Sin restricciones
   (el nombre puede variar). Volver a ejecutar el servidor y recargar Nexo.

`Failed to fetch` indica que el navegador no recibió una respuesta: puede ser
una suspensión de Pydroid, un proceso detenido o un fallo de conexión. No prueba
por sí solo un error de base de datos. La interfaz muestra instrucciones y un
botón Reconectar. No repite automáticamente escrituras: primero recupera los
datos para comprobar si la operación anterior quedó guardada.

Después de iniciar sesión, la dirección `http://127.0.0.1:8080/api/state`
responde con los datos JSON permitidos para esa cuenta. Sin sesión responde 401,
lo cual es normal. Si no abre, revisar Pydroid;
si Pydroid muestra una excepción, conservar su texto para diagnosticarla.

## Dos paneles: central y asesor

La identidad visual utiliza la fotografía real de M87* de EHT Collaboration,
distribuida por ESO: aparece en el acceso, la marca y los encabezados de los dos
paneles, incluyendo clientes, inmuebles, agenda y grabación de visitas. Las
hojas para imprimir conservan su fondo blanco. La imagen se carga desde
`https://cdn.eso.org/images/screen/eso1907a.jpg`; se necesita internet para su
primera carga. El service worker puede conservarla en la caché después de
abrir la aplicación bajo su control; esa caché depende del navegador. Si la
foto no carga, el fondo oscuro y los formularios siguen siendo legibles.
Crédito y ficha original: https://www.eso.org/public/images/eso1907a/.

1. En el primer acceso, crear el administrador. Si se actualiza una instalación,
   **conservar `data/`**: la base anterior se amplía sin borrar registros. Los
   datos existentes quedan visibles para el administrador, sin asignar, hasta
   que distribuya la cartera.
2. En **Equipo → Crear asesor**, definir nombre, usuario y contraseña inicial.
   Entregar esas credenciales al asesor. El rol lo define el servidor; crear un
   asesor no permite crear otro administrador.
3. En **Asignaciones**, asignar un cliente a un asesor y un inmueble a uno o
   varios asesores. También se pueden seleccionar al crear las fichas.
4. Cada asesor inicia sesión con su cuenta y ve **Mi panel**, **Mis clientes**,
   **Mis inmuebles**, **Mis visitas**, **Mis operaciones** y **Mi agenda**.
   Puede crear sus clientes, registrar visitas, grabar/transcribir, revisar y
   confirmar hojas, actualizar preferencias y organizar seguimientos.
5. El administrador consulta todo el equipo, su actividad, reportes,
   asignaciones y servicios. El panel central se actualiza cada 20 segundos
   mientras está visible y no hay un formulario abierto. También puede recargar.
6. Para cambiar de cuenta, tocar el perfil → **Mi cuenta → Cerrar sesión**.
   Desde Equipo se puede cambiar una contraseña o desactivar un asesor. Ambas
   acciones invalidan sus sesiones; desactivar conserva su historial.

El asesor no administra usuarios, conexiones, exportaciones globales ni la
cartera de inmuebles. Los permisos se verifican en cada ruta del servidor,
incluidos audios, documentos, transcripciones, coincidencias y consultas del
historial. Una propiedad compartida no permite ver clientes o visitas de otros
asesores. Las contraseñas se guardan con PBKDF2 y sal individual; las sesiones
usan una cookie HttpOnly, SameSite=Strict, duran 12 horas y se guardan por hash.

Transferir un cliente cambia la responsabilidad de sus visitas, operaciones y
seguimientos; concede al nuevo asesor acceso a los inmuebles de ese historial.
Conserva el nombre y los identificadores de quien registró/confirmó la visita.
No se retira el acceso a un inmueble mientras el asesor tenga registros
vinculados: primero se reasignan los clientes o actividades correspondientes.

**Para varios celulares se necesita un mismo servidor accesible por todos.**
`127.0.0.1` siempre es el propio teléfono. Ejecutar una copia del ZIP en cada
celular crea bases independientes, no un equipo compartido. Para trabajo real
con varios dispositivos, alojar esta versión Python en un servidor con HTTPS y
usar una URL común. El micrófono requiere HTTPS fuera de localhost.

Este ZIP permite ejecutar y probar ambos paneles con Pydroid. No incluye un
alojamiento publicado ni una dirección pública. El adaptador `worker/` conserva
el almacenamiento individual por cuenta de ChatGPT de la versión anterior;
**las cuentas de equipo y sus permisos están implementados en `server.py`**.
No desplegar ese adaptador como si ya incluyera esta función de equipo.

## Funciones implementadas

- Clientes: compradores, propietarios, inquilinos e inversores; presupuesto,
  zonas, tipo, necesidades, contacto, notas, documentos y visitas.
- Inmuebles: venta/alquiler, código, precio/moneda, características, propietario,
  dirección, fotografías propias, documentación y disponibilidad.
- Grabación de visitas con MediaRecorder y autorización explícita. Audio
  persistido y vinculado a cliente/inmueble. Captura de texto en vivo con
  SpeechRecognition si el navegador lo permite; también admite pegar texto y
  subir audio.
- Hoja automática con resumen, requisitos, presupuesto/moneda, zonas, gustos,
  objeciones, preguntas, oferta, interés expresado, acuerdos y seguimiento.
- Revisión/editado, borradores y confirmación. La confirmación es única,
  transaccional y deja la hoja de solo lectura. Opcionalmente actualiza
  preferencias y crea una actividad en la agenda. No rellena datos ausentes.
- Consulta del historial y resumen de la última visita confirmada antes de
  contactar al cliente. OpenAI es opcional; sin clave, extracción automática
  por patrones y consulta literal de los campos guardados.
- Coincidencias explicadas por operación, presupuesto, moneda, zona, tipo,
  dormitorios y estacionamiento. No convierte monedas sin una tasa explícita.
- Operaciones: contacto, visita, oferta, negociación, cierre y descartadas.
- Agenda: creación, edición, seguimiento, completar/cancelar, exportación ICS.
- Informes de actividad, cierres por moneda y exportación JSON.
- Impresión y PDF de hojas mediante el diálogo del navegador.
- Documentos persistidos y audios vinculados; archivos de hasta 80 MB.
- Avisos de actividades mientras la aplicación está abierta, si el usuario
  concede permiso. No hay notificaciones push mientras está cerrada.
- Recepción de reservas por WhatsApp y herramientas de Vapi, si se configuran
  sus servicios externos. Los horarios se revalidan al confirmar.

## Grabación y transcripción

El micrófono necesita localhost o HTTPS y permiso del navegador. El texto en
vivo depende de SpeechRecognition y no equivale a la transcripción definitiva.
Según el navegador, el reconocimiento de voz puede usar su servicio remoto.
Si no está disponible, el audio se conserva y se puede transcribir con
AssemblyAI o agregar notas manualmente. No se presenta una transcripción
simulada como si proviniera del audio.

## Servicios opcionales

Definir variables de entorno y reiniciar el servidor. `.env.example` documenta
los nombres; **no se carga automáticamente**. No colocar claves en código ni
en el navegador.

### Audio, hojas e historial con OpenAI

El administrador abre **Configuración → Conectar audio e IA**, elige OpenAI e
introduce su propia clave. Se guarda en `data/ai-settings.json`, con permisos
restrictivos y excluido del ZIP. El navegador recibe indicadores de conexión,
nunca la clave. La misma clave se usa para audio, extracción de la hoja y
preguntas sobre el historial. También admite `OPENAI_API_KEY` en el entorno,
que tiene prioridad sobre la clave local.

**Verificar OpenAI** realiza una solicitud breve de texto y consume una cantidad
pequeña de API. La transcripción debe comprobarse por separado con un audio real.
ChatGPT Plus no incluye este consumo de API. Guardar una clave no acredita su
validez, permisos ni saldo. Se necesita conexión a internet.

Modelo de texto por defecto: `gpt-4.1-mini`; `OPENAI_MODEL` puede cambiarlo.
Modelo de audio inicial: `gpt-4o-mini-transcribe`; también se pueden elegir
`gpt-transcribe` o `gpt-4o-transcribe-diarize`. El último identifica hablantes;
los demás no. OpenAI admite hasta **25 MB por archivo** y esta integración usa
WebM, MP3, MP4, M4A o WAV. Para archivos mayores hay que dividir la grabación;
esta versión no incorpora un conversor ni corte automático. Las nuevas
grabaciones se solicitan a 64 kbps para reducir su tamaño.

Los trabajos de OpenAI se ejecutan con dos transcripciones concurrentes
mediante hilos del servidor, sin bloquear las lecturas de los demás asesores
mientras el proveedor procesa el audio. El texto final se guarda en SQLite.
Repetir la solicitud sobre el mismo archivo en curso o completado reutiliza el
trabajo existente. Un trabajo interrumpido por un reinicio queda señalado y
puede iniciarse nuevamente desde el audio guardado; no se presenta como terminado.

Al detener una grabación o subir un audio, la conexión seleccionada lo transcribe
antes de preparar la hoja, incluso si hay un texto parcial capturado en vivo.
La hoja permanece como borrador hasta revisarla y confirmarla. Sin clave, se
puede organizar una conversación escrita con las reglas locales y consultar
literalmente los campos confirmados del historial.

### AssemblyAI como alternativa de transcripción

Se conserva la conexión anterior. En **Conectar audio e IA**, elegir AssemblyAI
y guardar su clave, o definir `ASSEMBLYAI_API_KEY`. Se guarda localmente en
`data/transcription-settings.json`. La selección del servicio se guarda en
`ai-settings.json`; `NEXO_TRANSCRIPTION_PROVIDER` permite definirla por entorno.
AssemblyAI transcribe en español con separación de hablantes. OpenAI sigue
siendo opcional para las hojas y la consulta del historial.

Los audios se envían al proveedor elegido, con el consentimiento de las personas
presentes. Cada proveedor puede cobrar el consumo según su cuenta y modelo.
Las credenciales no están incluidas en la descarga. Para una instalación alojada,
configurarlas como secretos del servidor.

Para actualizar, conservar **`data/` y `data_presentacion/`** si existen,
reemplazar los archivos del programa, reiniciar y recargar Nexo. El adaptador
`worker/` conserva la versión anterior; las cuentas del equipo, la demo aislada
y la nueva configuración de OpenAI corresponden a `server.py`.

### WhatsApp oficial de Meta

`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` para mensajes salientes. El asesor
revisa el mensaje y confirma el envío en la interfaz. Sin conexión puede abrir
`wa.me` y enviarlo personalmente desde WhatsApp.

Para reservas entrantes, además `WHATSAPP_VERIFY_TOKEN`, `META_APP_SECRET` y un
servidor HTTPS alcanzable desde Meta. Callback: `/webhooks/whatsapp`. Verificación
GET y firmas HMAC SHA-256 en POST. Conversación persistida: inmueble → horario →
nombre → confirmación. Deduplica identificadores de mensajes. `cancelar` propone
cancelar la próxima reserva y exige sí/no. No se implementaron plantillas Meta
para mensajes fuera de la ventana de conversación ni preguntas comerciales libres.

### Recepcionista de voz Vapi

`VAPI_SERVER_SECRET`. Configurar en Vapi el webhook `/webhooks/vapi` y el header
`x-vapi-secret` con el mismo secreto. Herramientas:

| Nombre | Argumentos |
|---|---|
| `listar_inmuebles` | ninguno |
| `consultar_disponibilidad` | `propertyId` opcional |
| `agendar_visita` | `propertyId`, `date`, `name`, `phone` |
| `consultar_mis_visitas` | `phone` |
| `cancelar_visita` | `eventId`, `phone` |

Copiar identificadores y horarios de resultados de herramientas. El asistente
debe leer el inmueble/fecha y solicitar confirmación antes de agendar/cancelar;
no debe inventar disponibilidad. El caller ID se usa si no viene `phone`.
Las cancelaciones verifican que la reserva corresponda a ese teléfono.
El número telefónico y el asistente Vapi se provisionan fuera de esta app.

La recepción usa un asesor, visitas de 45 minutos, días laborables y horario
9:00–18:00. `BOOKING_START_HOUR`, `BOOKING_END_HOUR` y `NEXO_TIMEZONE` permiten
ajustarlo. Excluye actividades pendientes superpuestas. No consulta freeBusy de
Google Calendar ni administra varios asesores con horarios independientes.

### Google Calendar

`GOOGLE_CALENDAR_TOKEN` y `GOOGLE_CALENDAR_ID` habilitan la ruta de envío
`POST /api/calendar` con `eventId`. El token debe tener acceso al calendario y
renovarse externamente si vence. No hay OAuth/renovación automática, freeBusy ni
sincronización bidireccional. La descarga ICS funciona sin estas credenciales.

## Acceso y copias

Por defecto escucha solo en localhost. Para acceso desde otra máquina, configurar
`HOST` y una `APP_PASSWORD` fuerte; usar un proxy HTTPS para el acceso real.
La contraseña adicional habilita HTTP Basic del navegador. Cada integrante
también usa su cuenta de Nexo. Crear el primer administrador desde localhost
antes de compartir el servidor. Detrás de un proxy HTTPS, definir `NEXO_HTTPS=1`
para marcar la cookie como Secure. Es un espacio de una inmobiliaria con roles
de administrador y asesor; no admite múltiples inmobiliarias independientes.

Respaldar **toda la carpeta `data/`** con la aplicación detenida o mediante un
snapshot consistente; incluye base de datos y archivos. La exportación JSON
conserva registros, pero no los adjuntos ni las sesiones de recepción. El registro
de auditoría en SQLite guarda escrituras y envíos. No reutiliza bases ni datos de
Vitalis.

## Verificación

```sh
python -m unittest discover -s tests -v
node --check public/app.js
node --check public/team.js
node tests/team-ui.test.mjs
node tests/audio-flow.test.mjs
node tests/presentation-ui.test.mjs
```

Los tests ejercitan rutas reales del handler sin abrir sockets: acceso,
sesiones, separación de carteras, archivos protegidos, transferencia conservando
autoría, revocación de acceso, límite de intentos de inicio de sesión y confirmación
atómica/idempotente, vínculos, archivos, protección de historial, extracción de
importes, negaciones, coincidencias y recepción por WhatsApp/voz. Las integraciones
externas requieren sus credenciales y una prueba real para considerarse activas.

## Publicación en dominio propio

Para alojar la versión completa con gerencia y asesores en `app.chatgo.ia.bo`, usar las instrucciones de [deploy/LEEME.md](deploy/LEEME.md). Incluye Docker, proxy HTTPS, creación privada del administrador y almacenamiento persistente. ClouDNS requiere la IP pública del servidor; el paquete por sí solo no configura el dominio ni contrata hosting.
