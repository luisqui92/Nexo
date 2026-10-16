# Nexo — ensayo para el lunes 19 de octubre de 2026

Este paquete contiene la aplicación local y una presentación de ocho diapositivas.
La demo usa personas y propiedades ficticias; las grabaciones nuevas provienen
del micrófono o del archivo que se sube. No se simula una transcripción de audio.

## Preparar antes de la reunión

1. Conservá un respaldo de tu carpeta `data/` y reemplazá solamente los archivos
   del programa por esta versión. No borres tus datos.
2. Detené `server.py`. En Pydroid abrí **`presentar.py`** y ejecutalo. En una
   computadora podés ejecutar `python presentar.py`.
3. El programa prepara `data_presentacion/`, separado de tus registros habituales.
   Incluye gerencia, Ana y Bruno, con carteras distintas, inmuebles, dos hojas
   confirmadas, un borrador, operaciones y agenda. La consola muestra los tres
   usuarios y sus contraseñas generadas para esta demo. También se guardan en
   `data_presentacion/accesos-demo.json`, únicamente en tu dispositivo.
4. Abrí Chrome en **http://127.0.0.1:8080** y entrá con **gerencia.demo** y su
   contraseña. Desde **Preparar presentación**, comprobá los datos y servicios.
5. Si vas a demostrar el audio automático, entrá a **Configuración → Conectar
   audio e IA**, elegí OpenAI e ingresá tu propia clave. Se necesita internet,
   facturación habilitada y saldo o capacidad de consumo. No compartas esa clave
   en el chat ni en las diapositivas.
6. Tocá **Verificar OpenAI**. Esa prueba comprueba la conexión de texto; después
   grabá un audio real de 30–60 segundos y comprobá también su transcripción.
   Revisá nombres, cifras y acuerdos. La verificación completa requiere ambas
   pruebas, no solamente guardar la clave.
7. En Android, permití el micrófono de Chrome, mantené Pydroid ejecutándose,
   configurá su batería sin restricciones y mantené Nexo visible al grabar.
8. Abrí **http://127.0.0.1:8080/presentacion.html**. Usá los botones o las flechas
   para pasar de diapositiva. **Guardar PDF** usa el diálogo de impresión.
   La foto de M87* necesita internet para su primera carga; la interfaz y las
   diapositivas tienen un fondo legible si la imagen no está disponible.

La presentación en PDF incluida es independiente del servidor y permite mostrar
la propuesta aunque no puedas ejecutar Nexo. No incluye un vídeo ni capturas de
una prueba real de transcripción.

## Guion de ocho minutos

**0:00–1:00 — Problema.**
“Lo que se conversa en una visita debe quedar vinculado al cliente y al inmueble.
Hoy ese contexto suele dispersarse entre notas, audios y mensajes.”

**1:00–2:00 — Gerencia.**
Mostrá Panel central, Equipo y Asignaciones. Ana y Bruno tienen carteras distintas.
Una propiedad compartida no permite ver los clientes del otro asesor.

**2:00–3:00 — Asesor.**
Tocá el perfil → Mi cuenta → Cerrar sesión. Entrá como **ana.demo** usando la
contraseña que mostró el programa. Abrí Lucía Mendoza y su inmueble de Queru Queru.
Mostrá el presupuesto, preferencias, documentos e historial.

**3:00–5:00 — Visita real breve.**
Creá una nueva visita para Lucía y su departamento. Confirmá la autorización
de las personas presentes y grabá este diálogo, o uno similar:

> “Estoy buscando un departamento con dos dormitorios y estacionamiento.
> Mi presupuesto es hasta 95 mil dólares. Me gustaron la ubicación y el balcón,
> pero quiero confirmar los gastos comunes. ¿Se permiten mascotas? Acordamos
> consultar las expensas y llamar mañana para coordinar una segunda visita.”

Detené la grabación. Con el servicio conectado, esperá la transcripción y la hoja.
Revisá cada campo, elegí una fecha de seguimiento y confirmá. Mostrá el audio
guardado, la hoja de solo lectura y la actividad creada en la agenda.

**5:00–6:00 — Retorno a gerencia.**
Cerrá sesión e ingresá como gerencia. Abrí Visitas y el nuevo registro de Ana.
Mostrá que la hoja queda vinculada al cliente, al inmueble y a quien la registró.

**6:00–7:00 — Propuesta.**
Presentá Bs90 mensuales por asesor como tarifa inicial a negociar, con una cuota
propuesta de 600 minutos de audio. También se pueden acordar una cuota corporativa
y cobro por visitas procesadas o minutos. Implementación y condiciones finales
se acuerdan por separado. No prometas minutos o consultas ilimitadas.

**7:00–8:00 — Siguiente paso.**
Proponé un piloto de 30 asesores durante 60 días. Medir uso, tiempo para preparar
hojas, seguimientos registrados, calidad de audio y costo real. Para miles de
usuarios todavía se necesita alojamiento compartido y validación de capacidad.

## Alternativa si falta internet o el servicio falla

El audio grabado permanece vinculado a la visita. Mostrá una hoja previamente
confirmada y la conversación original, o usá **Probar un ejemplo** y **Organizar texto sin IA** para generar
una hoja a partir de texto sin consultar un servicio externo. Aclaralo explícitamente: “Este texto es un ejemplo;
el audio automático requiere la conexión que estamos probando”. Si OpenAI está
configurado pero sin conexión, **Organizar texto sin IA** funciona con el
servidor local. También podés mostrar una hoja ya guardada y retomar las diapositivas.

No repitas compulsivamente **Transcribir**: OpenAI reutiliza el trabajo guardado
para ese mismo archivo cuando ya está en curso o completado. Si el servidor se
reinicia durante el procesamiento, consultá la visita y retomá desde el audio.

## Qué podés afirmar

- Dos paneles con cuentas y permisos: implementado en la versión Python local.
- Cartera, visitas, hoja revisable, agenda e historial: implementado.
- Grabación y conservación de audio: implementado; probar permisos del dispositivo.
- OpenAI para audio, hojas e historial: conexión implementada; requiere cuenta y
  una prueba real en tu dispositivo. Las pruebas entregadas utilizan un proveedor
  simulado para verificar el código, no certifican la calidad de una grabación real.
- WhatsApp, voz y calendario externo: requieren configurar los respectivos servicios.
- 1.800 asociados: oportunidad comercial; no equivalen a licencias pagadas ni a
  una prueba de 1.800 usuarios simultáneos.
- Facturación por visitas/minutos: propuesta comercial; no hay pasarela de pago
  ni límites de consumo contratados implementados.

## Volver al espacio habitual

Detené `presentar.py` y ejecutá `server.py`. Usa nuevamente tu carpeta `data/`.
Los cambios hechos en la demo permanecen únicamente en `data_presentacion/`.
Para mostrar varios dispositivos se necesita un mismo servidor accesible por
todos y HTTPS para el micrófono fuera de localhost. Este ZIP no incluye una URL
publicada ni el despliegue masivo.
