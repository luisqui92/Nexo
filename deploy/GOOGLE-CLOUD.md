# Nexo en Google Cloud

La versión actual funciona en una máquina virtual de **Compute Engine**, con el paquete Docker existente y datos en su disco. Google Cloud alojará Nexo; ClouDNS apuntará `app.chatgo.ia.bo` a su IP pública fija. No se ha creado ninguna máquina ni se ha cambiado DNS desde este entorno.

## Si ya existe una máquina

Abrir [Compute Engine → Instancias de VM](https://console.cloud.google.com/compute/instances), seleccionando el proyecto correcto. Revisar nombre, zona, sistema operativo, recursos e IP externa. Si aloja otros servicios, revisar primero puertos 80/443 y el proxy que ya utiliza antes de instalar Caddy. No reemplazar un servicio existente.

## Si solo existe el proyecto

Propuesta para el piloto, pendiente de revisar costo y confirmar creación en la consola:

| Ajuste | Propuesta |
| --- | --- |
| Nombre | nexo-app |
| Servicio | Compute Engine |
| Máquina | e2-medium, 4 GB de RAM |
| Sistema | Ubuntu 24.04 LTS |
| Disco de arranque | 40 GB, persistente |
| Aprovisionamiento | Estándar; sin interrupciones Spot |
| Red | IPv4 externa estática; HTTP y HTTPS permitidos |
| Dominio | app.chatgo.ia.bo |

La región se elige según disponibilidad, latencia y presupuesto. Esta propuesta es para ensayos y un piloto pequeño; no demuestra capacidad para 1.800 asesores. Ver el importe estimado en la consola **antes de crear**: máquina, disco, IP y tráfico generan cargos; los créditos disponibles dependen de tu cuenta. OpenAI se paga por separado. Configurar un presupuesto de facturación; una alerta de presupuesto no detiene por sí misma los gastos.

En Compute Engine, abrir **Crear instancia**, elegir estos ajustes y permitir HTTP y HTTPS. Reservar/asignar la IP externa como estática para conservarla al reiniciar o detener la máquina. No marcar eliminación automática del disco si se necesita conservarlo al borrar la VM. No abrir el puerto 8080.

Referencias oficiales: [crear una VM](https://docs.cloud.google.com/compute/docs/instances/create-vm-from-public-image), [IP externa fija](https://docs.cloud.google.com/compute/docs/ip-addresses/configure-static-external-ip-address).

## Instalar el proyecto

1. Abrir **SSH** junto a la instancia para entrar desde el navegador. La consola utiliza tu cuenta Google; no hace falta compartir tu contraseña conmigo.
2. Instalar Docker Engine y el complemento Docker Compose según [las instrucciones oficiales para Ubuntu](https://docs.docker.com/engine/install/ubuntu/). No ejecutar comandos destinados a otro sistema operativo.
3. Subir `Nexo-Servidor-Chatgo.zip` usando la transferencia de archivos de SSH en el navegador. Si el celular no muestra esa opción, usar la consola en vista de escritorio o un equipo con navegador de escritorio.

Referencia: [SSH desde el navegador](https://docs.cloud.google.com/compute/docs/connect/ssh-in-browser).

En la terminal de la VM, con el ZIP dentro del directorio personal:

```sh
sudo apt-get update
sudo apt-get install -y unzip
mkdir -p "$HOME/nexo-deploy"
unzip -n "$HOME/Nexo-Servidor-Chatgo.zip" -d "$HOME/nexo-deploy"
cd "$HOME/nexo-deploy/nexo-inmobiliaria/deploy"
cp -n .env.example .env
chmod 600 .env
nano .env
```

Completar `ACME_EMAIL` y conservar `NEXO_DOMAIN=app.chatgo.ia.bo`. No configurar claves de IA en este archivo; se ingresan después desde el panel central. Para esta primera instalación:

```sh
sudo docker compose config --quiet
sudo docker compose build app
sudo docker compose run --rm --no-deps app python scripts/create_admin.py
```

El último comando solicita nombre, usuario y contraseña de gerencia en privado. No sobrescribe usuarios si ya existen.

## Conectar ClouDNS e iniciar

En ClouDNS, zona `chatgo.ia.bo`: crear registro **A**, host **app**, valor **la IPv4 externa estática real de esta VM**, TTL **300**. Revisar posibles registros previos de ese host; no modificar el dominio principal ni sus servidores DNS.

Cuando el registro apunte a la VM:

```sh
sudo docker compose up -d
sudo docker compose ps
sudo docker compose logs --tail 80 caddy
```

Caddy obtiene el certificado HTTPS si DNS, salida a internet y entrada TCP 80/443 funcionan. El permiso UDP 443 es opcional para HTTP/3; HTTPS convencional funciona por TCP. Si existe un firewall dentro de Ubuntu, permitir allí también TCP 80/443 conservando el acceso SSH.

Abrir `https://app.chatgo.ia.bo` desde el celular. Iniciar sesión como gerencia, configurar OpenAI y crear asesores. Realizar las pruebas de audio, aislamiento de usuarios y persistencia descritas en [LEEME.md](LEEME.md).

Los volúmenes Docker sobreviven a reinicios de contenedores y de la VM mientras se conserve su disco. No protegen frente a borrar ese disco. Hacer respaldos y copiarlos a otro almacenamiento. Como estos comandos usan `sudo docker`, el respaldo también requiere `sudo python3 backup.py`. No ejecutar `docker compose down -v`.

Pendiente para considerar el despliegue terminado: VM conectada, contenedores construidos y ejecutándose, DNS verificado, certificado emitido y una visita real grabada/transcrita desde el celular. Ninguna de estas comprobaciones se sustituye por las pruebas locales del código.
