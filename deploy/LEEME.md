# Publicar Nexo en app.chatgo.ia.bo

ClouDNS administra el nombre; el programa necesita un servidor Linux con Docker Engine y Docker Compose. Esta carpeta despliega la versión Python completa, con cuentas de gerencia y asesores. No usa el adaptador antiguo de `worker/`.

**Estado:** paquete preparado; falta ejecutar en el servidor, configurar DNS y comprobar HTTPS y audio real. Esta configuración es para un piloto. No se validó capacidad para 1.800 asesores simultáneos. Como punto de partida para el piloto: VPS de 2 vCPU, 4 GB de RAM y disco SSD de 40 GB, ampliable según visitas, tamaño de audio y uso concurrente. El hosting, dominio e IA tienen costos independientes.

## 1. Preparar el servidor

Usar Linux actualizado con Docker Engine y el complemento Compose v2. Subir el proyecto completo por SFTP/SSH, por ejemplo a `/opt/nexo`. Ejecutar lo siguiente desde `/opt/nexo/deploy`, con una cuenta que pueda usar Docker:

```sh
cp .env.example .env
chmod 600 .env
nano .env
docker compose config --quiet
docker compose build app
docker compose run --rm --no-deps app python scripts/create_admin.py
```

En `.env`, conservar `NEXO_DOMAIN=app.chatgo.ia.bo` y completar `ACME_EMAIL` con un correo real. El comando de administración pide usuario y contraseña en la terminal; la contraseña no aparece en el historial. No reemplaza cuentas existentes. No publicar antes de crear este administrador.

Usar una contraseña exclusiva, de al menos 10 caracteres. No usar las cuentas de `presentar.py` ni copiar `data_presentacion` al servidor. La imagen no incorpora archivos de datos, claves ni carpetas de demostración. La aplicación persiste SQLite, audios y ajustes de IA en el volumen `nexo_data`.

## 2. Configurar ClouDNS

En la zona **chatgo.ia.bo**, agregar este registro, cuando el proveedor entregue la IP pública real:

| Tipo | Host | Valor | TTL |
| --- | --- | --- | --- |
| A | app | IP pública IPv4 del servidor | 300 |

No modificar los servidores DNS ni los registros del dominio principal. Si `app` ya tiene un registro A, AAAA o CNAME, revisar su uso y corregir el conflicto antes de continuar. Agregar AAAA únicamente si el servidor tiene IPv6 público funcionando. No usar `127.0.0.1`, una IP privada ni una dirección inventada. Si el proveedor solicita el nombre completo, usar `app.chatgo.ia.bo`.

## 3. HTTPS e inicio

Permitir entrada TCP 80 y 443 y UDP 443 en el firewall del proveedor y del servidor. Mantener SSH accesible según su configuración. No exponer 8080 ni el directorio de datos. El servidor necesita salida HTTPS para certificados e IA.

```sh
docker compose up -d
docker compose ps
docker compose logs --tail 80 caddy
```

Caddy emite el certificado automáticamente cuando DNS y puertos están listos. Abrir **https://app.chatgo.ia.bo** e iniciar sesión con el administrador creado. El acceso requiere cuentas de Nexo; los registros no son públicos. Caddy redirige HTTP a HTTPS y permite el micrófono en este dominio. Las sesiones usan cookies Secure y HttpOnly. El backend solo es accesible dentro de la red Docker. No publicar su puerto con `-p` ni agregar `ports` al servicio `app`.

En el panel central, crear asesores, cargar y asignar clientes e inmuebles. En configuración, ingresar una clave de OpenAI propia. La clave queda en el volumen privado y no se devuelve al navegador. La prueba de clave verifica acceso de texto; además realizar una grabación real para verificar transcripción. No pegar claves en chats ni incluirlas en ZIP públicos.

## 4. Prueba desde un celular

1. Abrir el subdominio desde Chrome en datos móviles, fuera de la red del servidor.
2. Iniciar sesión como asesor y comprobar que ve sus clientes e inmuebles asignados.
3. Crear una visita, aceptar el micrófono y grabar 30–60 segundos con consentimiento de quienes participen. Mantener la pantalla desbloqueada.
4. Detener y comprobar audio guardado, transcripción, hoja de visita y confirmación.
5. Entrar como otro asesor y verificar que no puede abrir el audio ni la visita del anterior. Comprobar la vista de gerencia.
6. Reiniciar con `docker compose restart app` y verificar que cuentas, visitas y audio siguen presentes.

Sin saldo/clave válida o conexión al proveedor, el audio queda guardado pero no se transcribe automáticamente. Se pueden escribir notas y usar la extracción de texto local. El máximo para transcribir con OpenAI es 25 MB por archivo. No se hizo esta prueba real en el entorno de preparación.

## 5. Respaldo y mantenimiento

```sh
python3 backup.py
```

El respaldo detiene brevemente Nexo para copiar juntos SQLite, ajustes y audios; ejecutar fuera de visitas activas. Copiar el archivo cifrado a otro almacenamiento y probar recuperación periódicamente. Contiene claves de IA y datos privados. Conserva permisos de propietario; no subirlo a un enlace público. Este script crea respaldos manuales, no una programación automática.

Para restaurar en un servidor con esta misma configuración, copiar el respaldo dentro de `deploy/backups` y ejecutar, **solo si se ha decidido reemplazar el contenido actual del volumen**:

```sh
docker compose stop app
docker compose run --rm --no-deps -T --entrypoint tar app xzf - -C /app/data < backups/ARCHIVO.tar.gz
docker compose up -d
```

Restaurar preferentemente en un volumen vacío; extraer encima conserva archivos adicionales que no existían en el respaldo. Asegurar también la copia de `.env`, sin compartirla públicamente. **No ejecutar `docker compose down -v`: elimina datos y certificados.** Para actualizar código, hacer respaldo primero y luego `docker compose build app` y `docker compose up -d`.

La aplicación usa SQLite y un servidor Python sencillo, con dos trabajos de transcripción a la vez. Antes de incorporar toda la red de asesores, medir carga y migrar según resultados a un servidor de aplicación y base de datos apropiados, cola de trabajos y almacenamiento de audios ampliable. No hay facturación automática ni infraestructura de alta disponibilidad en este paquete.
