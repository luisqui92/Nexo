# La jornada — inicio de Nexo

La pantalla de inicio de administración y asesores usa una mesa de trabajo con
agenda, hojas por revisar y conversaciones. Se retiraron de este inicio las
cuatro tarjetas de totales, el banner con fotografía y la tabla de métricas.
Los informes y la gestión del equipo siguen disponibles desde sus secciones.

- **Hoy**, **Próximos** y **Atrasados** filtran actividades pendientes por día
  según el calendario local del navegador, como el resto de la agenda. Atrasados
  contiene días anteriores a hoy. Se excluyen completadas y canceladas.
- **Después de la visita** muestra los borradores más recientes y abre sus hojas.
- Administración ve clientes sin asignar y accesos de equipo; el asesor ve sus
  operaciones abiertas. Los datos siguen limitados por los permisos del servidor.
- La cartera muestra inmuebles disponibles con enlaces a la ficha privada.
- Los botones abren los formularios existentes de grabación, agenda, asignación,
  cuentas y propiedades. No se generaron registros ni estadísticas ficticias.

La nueva composición usa fondo cálido, tipografía editorial de sistema, agenda
sobre papel y cuaderno verde. `public/workdesk.css` se aplica al nuevo inicio.
Los accesos del menú pasan a llamarse La jornada y Mi jornada. No usa fuentes
externas ni necesita claves. El service worker sube a nexo-shell-v10 para incluir
la nueva hoja de estilos.

Validación: pruebas de interfaz del equipo (filtros, orden, texto escapado,
borradores, acciones por rol), marketplace y flujo de audio; sintaxis JavaScript.
No hubo revisión visual en un navegador real en este entorno.

Actualizar desde SSH de la VM:

```bash
cd "$HOME/nexo-deploy/nexo-inmobiliaria/deploy"
git pull --ff-only && sudo docker compose up -d --build app
```

Abrir `https://app.chatgo.ia.bo/#inicio` y recargar con Ctrl+Shift+R.
