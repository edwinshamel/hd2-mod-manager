# HD2 Mod Manager

Gestor de mods para **Helldivers 2** en Linux, con interfaz gráfica GTK4 + Libadwaita y auto-actualización via GitHub.

---

## Requisitos

| Componente | Version minima |
|---|---|
| Python | 3.11+ |
| GTK | 4.0 |
| Libadwaita | 1.x |
| Git | cualquiera |
| Helldivers 2 | instalado via Steam |

**Distribuciones soportadas:** Debian/Ubuntu, Fedora/RHEL, Arch Linux y derivados.

---

## Instalacion

Ejecuta este unico comando en una terminal:

```bash
git clone https://github.com/edwinshamel/hd2-mod-manager.git ~/hd2-mod-manager && bash ~/hd2-mod-manager/install.sh
```

El instalador automaticamente:

1. Detecta tu gestor de paquetes (apt / dnf / pacman)
2. Instala todas las dependencias del sistema
3. Crea el acceso directo en el menu de aplicaciones (`HD2 Mod Manager`)
4. Refresca la base de datos de aplicaciones de tu escritorio

Tras la instalacion puedes abrir la app desde el menu o con:

```bash
python3 ~/hd2-mod-manager/main.py
```

---

## Primera ejecucion

Al abrir la app por primera vez, si la ruta de Helldivers 2 no es detectada automaticamente, aparecera un dialogo de bienvenida.

Haz clic en **Configurar ahora** y selecciona la carpeta raiz del juego. Por ejemplo:

```
/mnt/storage/SteamLibrary/steamapps/common/Helldivers 2
```

La app verificara que dentro de esa carpeta exista el subdirectorio `data/`. Si no lo encuentra, mostrara un error y no guardara la ruta.

---

## Como instalar un mod

Los mods **no se descargan automaticamente**. Debes obtener el ZIP manualmente desde [Nexus Mods](https://www.nexusmods.com/helldivers2) u otra fuente.

1. Descarga el mod como archivo `.zip`
2. Abre HD2 Mod Manager
3. Haz clic en el boton **Instalar mod** (esquina superior izquierda)
4. Selecciona el archivo `.zip` en el selector de archivos
5. Edita el nombre del mod si lo deseas (por defecto usa el nombre del archivo)
6. Haz clic en **Instalar**

La app extrae los archivos del ZIP directamente en la carpeta `data/` del juego. Si algun archivo del juego es sobreescrito, se guarda un backup automatico en `~/hd2-mod-manager/backups/<nombre-del-mod>/`.

---

## Gestion de mods instalados

Cada mod aparece como una fila en la lista principal con:

- **Nombre** del mod y fecha de instalacion
- **Cantidad de archivos** instalados
- **Switch** para activar o desactivar sin desinstalar
- **Boton de verificacion** (icono de check): comprueba que todos los archivos del mod esten presentes en el juego
- **Boton de actualizacion** (icono de descarga): permite reemplazar el mod con una version nueva
- **Boton de desinstalacion** (icono de papelera): elimina el mod y restaura los archivos originales del juego

### Activar / desactivar un mod

Usa el switch en la fila del mod. Al desactivar:

- Los archivos del mod son reemplazados por los originales (desde el backup)
- Los archivos del mod se guardan temporalmente en `~/hd2-mod-manager/disabled/<nombre-del-mod>/`

Al reactivar, los archivos del mod vuelven a la carpeta del juego.

### Verificar integridad

Haz clic en el boton con icono de check. Aparece un dialogo con la lista de todos los archivos del mod y si cada uno esta presente (`✓`) o falta (`✗`).

### Actualizar un mod

1. Descarga el nuevo ZIP del mod
2. Haz clic en el boton de actualizacion del mod correspondiente
3. Selecciona el nuevo ZIP

La app compara el hash MD5 del nuevo ZIP con el instalado. Si son iguales, informa que el mod ya esta actualizado. Si son distintos, desinstala la version antigua y reinstala la nueva automaticamente.

### Desinstalar un mod

1. Haz clic en el boton de papelera del mod
2. Confirma en el dialogo de advertencia

La app elimina todos los archivos del mod del juego y restaura los archivos originales desde el backup. Si no habia backup de algun archivo (porque no existia antes de instalar el mod), ese archivo simplemente se elimina.

---

## Configuracion

Haz clic en el boton de engranaje (esquina superior derecha) para abrir la ventana de configuracion.

- **Carpeta de instalacion**: ruta raiz de Helldivers 2. Haz clic en **Cambiar** para seleccionarla con un selector de carpetas grafico.
- **Estado**: indica si la ruta es valida (detecta la subcarpeta `data/`) o invalida.

La configuracion se guarda en `~/hd2-mod-manager/config.json`.

---

## Actualizaciones de la app

Al iniciar, la app consulta en segundo plano los tags del repositorio en GitHub. Si existe una version nueva (comparacion semantica), aparece un dialogo con dos opciones:

- **Despues**: cierra el dialogo sin hacer nada
- **Actualizar ahora**: ejecuta `git pull origin master` en la carpeta de instalacion y reinicia la app automaticamente

Para publicar una nueva version basta con crear un tag en el repositorio:

```bash
git tag v1.1.0 && git push origin master --tags
```

---

## Estructura de archivos

```
~/hd2-mod-manager/
├── main.py              # Punto de entrada
├── ui.py                # Interfaz GTK4 + Libadwaita
├── mod_manager.py       # Logica de instalacion, backups, toggle, verificacion
├── updater.py           # Auto-actualizacion via GitHub tags
├── logger.py            # Sistema de logs en 3 niveles
├── version.py           # VERSION y REPO
├── install.sh           # Instalador de un solo comando
├── config.json          # Ruta del juego (generado en primera ejecucion)
├── mods_index.json      # Indice de mods instalados (generado automaticamente)
├── mods/                # Carpeta interna por mod (metadatos)
├── backups/             # Archivos originales del juego antes de cada mod
├── disabled/            # Archivos de mods desactivados temporalmente
└── logs/
    ├── info/            # Eventos normales  (YYYY-MM-DD.log)
    ├── debug/           # Detalle tecnico   (YYYY-MM-DD.log)
    └── error/           # Errores           (YYYY-MM-DD.log)
```

Los archivos `config.json`, `mods_index.json`, `mods/`, `backups/`, `disabled/` y `logs/` estan excluidos del repositorio via `.gitignore` y son locales a cada usuario.

---

## Logs

Los logs se generan diariamente en `~/hd2-mod-manager/logs/` separados por nivel:

| Carpeta | Contenido |
|---|---|
| `logs/info/` | Acciones del usuario, instalaciones, actualizaciones |
| `logs/debug/` | Detalle de cada operacion (archivos procesados, rutas, hashes) |
| `logs/error/` | Errores y excepciones con traza completa |

Cada archivo tiene el formato `YYYY-MM-DD.log` y se crea automaticamente al iniciar la app.

---

## Desinstalacion manual

```bash
rm -rf ~/hd2-mod-manager
rm -f ~/.local/share/applications/hd2-mod-manager.desktop
update-desktop-database ~/.local/share/applications/
```

> Antes de desinstalar la app, desinstala todos los mods desde la interfaz para que los archivos originales del juego sean restaurados correctamente.

---

## Repositorio

[https://github.com/edwinshamel/hd2-mod-manager](https://github.com/edwinshamel/hd2-mod-manager)
