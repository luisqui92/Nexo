# Portal público, asesores independientes e inmobiliarias

La versión completa funciona con el servidor Python y Docker de Google Cloud.
El adaptador antiguo para Workers no implementa el registro, el portal ni los
espacios independientes. No usarlo para desplegar esta versión.

## Rutas

- `/explorar`: mapa y lista públicos, filtros, fichas y contacto por WhatsApp.
- `/explorar?ejemplos=1`: el mismo mapa con seis casas ficticias para demostración.
- `/registro`: alta de un asesor independiente o una inmobiliaria.
- `/inmueble/<id>`: enlace público para compartir un inmueble publicado.
- `/asesor/<id>`: publicaciones disponibles de un anunciante.
- `/#inicio`: acceso al panel privado existente.
- `/#publicaciones`: selección de inmuebles, ubicación, fotos y contacto público.
- `/#solicitudes`: consultas recibidas y estado del seguimiento.
- `/#plataforma`: administración de Nexo, solo para el administrador principal.

## Casas de ejemplo para el mapa

El enlace **Ver casas de ejemplo** abre seis casas ilustrativas en Cala Cala,
Queru Queru, Sarco, Tiquipaya, Tupuraya y Colcapirhua. Incluyen precios de venta
y alquiler en USD y Bs, características y una ilustración original por casa.
Cada ficha, imagen y marcador están identificados como ejemplo. Las posiciones
son puntos ilustrativos de las zonas y no identifican propiedades reales.

Este catálogo es de solo lectura: no crea registros, usuarios, publicaciones
reales ni solicitudes. Las casas de ejemplo no tienen teléfono ni permiten
contactos o reservas. Se pueden filtrar, explorar y compartir por enlace.
**Ver inmuebles reales** vuelve al catálogo de publicaciones auténticas; los
ejemplos no se mezclan con esa búsqueda ni cambian las carteras privadas.

## Ambientes ficticios y vista 360°

Las seis fichas de ejemplo incluyen una galería: fachada ilustrada, dormitorio
ficticio y cocina ficticia. Comparten los mismos dos interiores generados con IA
y una panorámica de sala, con aviso visible; no representan ofertas reales.

**Abrir vista 360°** carga una imagen equirectangular 2:1 de la sala en un visor
esférico local con WebGL. Permite mirar alrededor con el dedo, mouse o flechas,
acercar, alejar y restablecer. Se carga únicamente al tocar el botón, sin claves
ni librerías externas. Si el dispositivo no soporta el visor o falla la imagen,
se mantienen la galería y un enlace a la panorámica. El visor libera sus recursos
al cerrar o cambiar de ficha.

Es una demostración de un ambiente. No es un recorrido completo ni permite
caminar por las habitaciones. Los archivos WebP están en
`public/examples/interiores/`, suman menos de 700 KB y se sirven desde Nexo.
No se añadieron campos de 360° ni carga de panorámicas a los inmuebles reales.

## Qué hace cada cuenta

Un asesor independiente tiene su espacio propio: administra sus inmuebles,
clientes y visitas, publica su cartera y recibe consultas. La cuenta de una
inmobiliaria crea un espacio para su gerente, que puede dar de alta asesores y
asignarles cartera. Los asesores del equipo conservan los permisos de cartera
asignada; las publicaciones de la inmobiliaria las gestiona su administración.

Las cuentas y registros existentes se migran automáticamente al espacio
principal, sin cambiar sus contraseñas ni publicar sus inmuebles. El administrador
existente del espacio principal recibe el acceso de administración de Nexo.
Esa administración puede suspender cuentas, espacios y publicaciones, atender
reportes y habilitar IA. Su panel de CRM sigue limitado a su propio espacio;
no obtiene acceso a clientes, audios ni documentos de otros espacios.

## Publicar un inmueble

1. Registrá o editá su ficha privada con título, zona, precio, características y
   descripción. Los inmuebles de demostración no se publican.
2. Entrá a **Publicaciones → Ubicar y publicar** o desde **Publicar en el portal**
   en la ficha del inmueble.
3. Marcá su ubicación en el mapa, ingresá coordenadas o usá la ubicación del
   dispositivo cuando estés en el inmueble. Confirmá ciudad y WhatsApp público.
4. Agregá fotos y seleccioná hasta 10. Las fotos nuevas que se suben desde este
   formulario se reducen en el navegador a un máximo de 1600 px por lado y se
   guardan como JPEG. El archivo original admitido es de hasta 8 MB.
5. Elegí **Publicar en el portal**, confirmá tu autorización y guardá.

La ficha pública copia únicamente título, zona, ciudad, operación, tipo,
precio/moneda, características, descripción, fotos elegidas y contacto del
responsable. Las coordenadas públicas se redondean a dos decimales; la ubicación
exacta queda en la ficha privada. No se comparten propietario, dirección,
documentos, notas internas, clientes, audios ni hojas de visita.

Para reflejar cambios de precio o descripción del CRM en el portal, volvé a
guardar la publicación. Una propiedad vendida, alquilada, reservada o pausada
deja de verse automáticamente porque solo se muestran inmuebles disponibles.
Pausar la publicación retira también sus fotos del acceso público. Suspender la
cuenta o el espacio tiene el mismo efecto. Republicar no quita una suspensión
aplicada por Nexo.

## Consultas y solicitudes

Un visitante puede consultar sin registrarse. La solicitud requiere nombre,
teléfono y autorización para entregarlos al anunciante. Se conserva en
**Solicitudes**, donde el responsable puede marcarla como contactada o archivada.
La solicitud no crea un cliente ni una cita confirmada automáticamente. El
horario debe coordinarse con la persona interesada.

Los reportes públicos se revisan desde la administración de Nexo. Hay límites
de registros y solicitudes por conexión. El correo indicado en el registro es
un dato de contacto; esta versión no envía correos de verificación ni recuperación.
No hay cobros ni suscripciones automáticas en este alcance.

## Audio, IA e integraciones existentes

La IA permanece habilitada en el espacio principal existente según su
configuración. Los espacios nuevos se crean con IA deshabilitada y el
administrador de Nexo puede habilitarla individualmente. Registrar una cuenta no
autoriza a consumir la clave compartida ni modificar la conexión global.
La organización local de notas está disponible sin IA. No hay cuotas ni cobro
por minutos en esta versión.

Las conexiones de WhatsApp/Vapi y Google Calendar preexistentes pertenecen al
espacio principal. Las nuevas cuentas pueden abrir WhatsApp con su propio
contacto y usar las funciones locales del panel. Los webhooks del espacio
principal no pueden consultar ni reservar inmuebles de otros espacios.

## Mapas y despliegue

Leaflet 1.9.4 y MarkerCluster 1.5.3 se cargan desde el CDN de unpkg. Si la librería
o las teselas no cargan, la lista y las fichas siguen disponibles. Se usa
OpenStreetMap como cartografía predeterminada; el mapa muestra la atribución.
Para un lanzamiento con mayor tráfico, configurá un proveedor de teselas con
capacidad y condiciones acordes al uso, conservando los créditos exigidos.

Variables opcionales en `deploy/.env`:

```dotenv
NEXO_MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png
NEXO_MAP_PROVIDER=OpenStreetMap
```

El proveedor y su clave, si va en la URL de teselas, son visibles en el navegador.
Usá una clave apta para mapas públicos y restringida por dominio. No uses claves
privadas de Google Cloud ni de OpenAI en esta variable.

Actualización en la VM:

```bash
cd "$HOME/nexo-deploy/nexo-inmobiliaria/deploy"
sudo python3 backup.py
git pull --ff-only && sudo docker compose up -d --build
sudo docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

La recarga de Caddy habilita la ubicación del dispositivo en el dominio y ajusta
el encabezado de referencia que necesita la cartografía. La migración es aditiva
y usa el volumen existente. Después, recargá la web con Ctrl + Shift + R.

Una base con cuentas de varios espacios debe seguir usando esta versión o una
posterior. Las versiones anteriores no filtran por espacio y no son una opción
de reversión sobre esa misma base. Conservá un respaldo previo al cambio para
recuperaciones completas.

## Verificación

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/marketplace-ui.test.mjs
node tests/team-ui.test.mjs
node tests/audio-flow.test.mjs
```

Las pruebas incluyen migración desde SQLite anterior, separación de espacios,
acceso anónimo, archivos privados, consentimiento, fotos seleccionadas, retiro
de publicaciones, moderación, solicitudes, filtros y límites, y restricción de
consumo de IA. La visualización de mapas y los permisos del navegador requieren
verificación manual en el dominio desplegado; no se ejecutaron pruebas de carga
para 1800 o 3000 usuarios.


### Si OpenStreetMap muestra «Access blocked» o 403

El proveedor necesita identificar el sitio mediante el encabezado `Referer`.
Los tres mapas envían únicamente el origen de Nexo a servidores externos con
`referrerPolicy: strict-origin-when-cross-origin`; no envían rutas ni consultas.
Caddy y Python usan la misma política. No usar `same-origin` ni `no-referrer`
para estas solicitudes de mapas.

Una actualización del contenedor `app` no recarga la configuración de Caddy.
Después de actualizar, ejecutar desde `deploy`:

```bash
sudo docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Luego recargar el navegador con Ctrl+Shift+R. Si persiste el bloqueo, verificar
el `Referer` de una solicitud de tesela en la pestaña Red del navegador. Si el
proveedor sigue bloqueando con la identificación correcta, revisar el bloqueo
con él o configurar otro proveedor contratado mediante `NEXO_MAP_TILE_URL`.
No rotar subdominios para eludir el bloqueo.
