# Trazabilidad de OP – Hilado y Tela

Aplicación de escritorio (Python + PySide6) para consultar la trazabilidad y el costo de las
Órdenes de Producción (OP) de una empresa textil: compras de hilado, servicios de tejeduría,
tintorería, acabados y envíos a CMT. Permite buscar una OP o un lote de OPs, ver el resumen por
categoría, bajar al detalle de cada movimiento (guía, OC, factura), exportar a Excel y revisar un
dashboard con gráficos.

Funciona igual en **Windows** y **macOS**. Abajo, cada comando aparece para los dos sistemas.

---

## 1. Descargar los datos de prueba

Los datos de prueba vienen en un archivo comprimido, **`migracion.zip`**, con tres bases SQLite:
del siguiente link: [drive](https://drive.google.com/drive/folders/1UHJtMbRVIWMLGmJW5TV-rpZyKL6yOYNc?usp=sharing)

| Archivo | Contenido |
|---|---|
| `control_hilados.db` | Movimientos y consumo de hilado |
| `control_tejidos.db` | Movimientos de tela (tejeduría, tintorería, CMT) |
| `resumen_op.db` | Resumen por OP y categoría |

1. Descarga `migracion.zip`.
2. Déjalo en la carpeta **Descargas**, que es donde el navegador lo guarda por defecto:
   - **macOS:** `/Users/<tu_usuario>/Downloads`
   - **Windows:** `C:\Users\<tu_usuario>\Downloads`
3. **No hace falta descomprimirlo.** El script del paso 2 lo hace por ti.

> Si tu navegador guarda las descargas en otra carpeta, mueve el `.zip` a Descargas antes de
> seguir.

---

## 2. Preparar las bases de datos (`setup_db_.py`)

Desde la carpeta del proyecto, ejecuta:

**macOS (Terminal)**
```bash
cd ruta/al/proyecto/INTERFAZ-TRAZABILIDAD-OPS
python3 setup_db_.py
```

**Windows (PowerShell)**
```powershell
cd ruta\al\proyecto\INTERFAZ-TRAZABILIDAD-OPS
python setup_db_.py
```

El script hace lo siguiente:

1. Busca `migracion.zip` en la carpeta Descargas del usuario. Si el navegador lo renombró (por
   ejemplo, `migracion (1).zip`), usa el `.zip` más reciente que contenga las tres bases.
2. Crea la carpeta **`migracion/`** dentro del proyecto.
3. Descomprime ahí las tres bases `.db` y verifica que sean bases SQLite válidas.

Si `migracion/` ya tiene las bases, el script pregunta antes de reemplazarlas. Si el `.zip` está
en otra carpeta, indica la ruta directamente:

```bash
python3 setup_db_.py --zip /ruta/al/migracion.zip
```

Solo usa la librería estándar de Python, así que puedes correrlo antes de instalar las
dependencias del paso 3. Al terminar, el proyecto debe verse así:

```
INTERFAZ-TRAZABILIDAD-OPS/
├── migracion/
│   ├── control_hilados.db
│   ├── control_tejidos.db
│   └── resumen_op.db
├── main.py
└── ...
```

---

## 3. Instalación

### Requisitos

- **Python 3.11 o superior.** Para verificarlo: `python3 --version` en macOS o
  `python --version` en Windows.
  Si no lo tienes, descárgalo de <https://www.python.org/downloads/>. En Windows, marca la
  opción **"Add Python to PATH"** durante la instalación.

### Pasos

Todos los comandos se ejecutan **dentro de la carpeta del proyecto**.

**1. Crear un entorno virtual**

| macOS | Windows |
|---|---|
| `python3 -m venv venv` | `python -m venv venv` |

**2. Activar el entorno virtual**

| macOS | Windows |
|---|---|
| `source venv/bin/activate` | `venv\Scripts\Activate.ps1` |

Cuando el entorno está activo, la consola muestra `(venv)` al inicio de la línea.

> **Windows:** si PowerShell responde que la ejecución de scripts está deshabilitada, ejecuta
> primero `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activar el
> entorno. El permiso solo dura mientras esa ventana esté abierta.

**3. Instalar las dependencias**

```bash
pip install -r requirements.txt
```

Esto instala `pandas`, `PySide6` (interfaz y gráficos) y `openpyxl` (lectura y escritura de
Excel).

---

## 4. Uso

### Abrir la aplicación

Con el entorno virtual activo y **desde la carpeta del proyecto**:

| macOS | Windows |
|---|---|
| `python3 main.py` | `python main.py` |

La barra inferior debe decir `Hilado: [OK] | Tejidos: [OK] | Resumen: [OK]`. Si alguna dice
`Falta`, revisa la sección **Solución de problemas**.

> Para usar bases que están en otra carpeta, pásala como argumento:
> `python main.py /ruta/a/otra/carpeta`

### Buscar una OP

1. Escribe el número en **OP Referencial**, por ejemplo `26997`.
2. Presiona **Enter** o haz clic en **Buscar**.
3. La pestaña **📋 Resumen** muestra una fila por categoría: kg netos, valorizado en US$ y costo
   unitario ponderado. Las filas siguen el orden del flujo productivo: hilado → tejeduría →
   tintorería → CMT.

Otras OPs para probar: `25553`, `24664`, `25559`.

> **Cómo leer los signos:** los valores positivos son entradas o costos (compras, servicios,
> consumo). Los negativos son envíos o salidas hacia la siguiente etapa (a tejeduría, a
> tintorería, a CMT).

### Buscar un lote de OPs desde Excel

1. Prepara un Excel con una columna llamada **`OP`** y un número de OP por fila:

   | OP |
   |---|
   | 26997 |
   | 25553 |
   | 24664 |

2. Marca la casilla **Por lote (Excel)**.
3. Haz clic en **📁 Cargar Excel** y elige el archivo.
4. Haz clic en **Buscar Lote**. Los resultados se agrupan por OP, en el orden del Excel.

### Ver el detalle de una categoría

En cualquier fila del resumen, haz clic en **🔍 Ver Detalle**. Se abre una ventana con cada
movimiento: fecha, proveedor, guía, OC, factura, kg, US$ y costo unitario.

- En la columna **Kgs**, verde son entradas y rojo son salidas.
- Haz clic en un encabezado para ordenar por esa columna.
- El **pie de totales** (movimientos, kg, US$ y costo unitario ponderado) debe coincidir con la
  fila del resumen.

### Exportar a Excel

- **📊 Exportar a Excel** en la ventana principal exporta el resumen.
- **📊 Exportar a Excel** en la ventana de detalle exporta los movimientos, con una fila TOTAL
  al final.

Por defecto, el archivo se guarda en la carpeta Descargas.

### Dashboard

La pestaña **📈 Dashboard** muestra la búsqueda actual (una OP o un lote) en gráficos:

- **Indicadores:** OPs analizadas, servicios en US$, compra de tela en US$ y % de merma de
  tejeduría.
- **Valorizado neto por categoría:** entradas y costos en azul, envíos en rojo.
- **Costo de servicios por tipo:** de mayor a menor.
- **Balance de hilado en tejeduría (kg):** enviado, consumido, merma y saldo sin consumir.
- **Top 10 OPs por costo de servicios:** solo en búsqueda por lote.

Pasa el cursor sobre una barra para ver su valor exacto.

> "Compra de hilado" no se usa en el dashboard, porque una misma compra puede aparecer completa
> en varias OPs. Su monto sí aparece en la pestaña Resumen.

### Tema claro u oscuro

En la esquina inferior derecha, el selector **Tema** ofrece tres opciones: **Sistema** (sigue el
modo claro u oscuro del sistema operativo), **Claro** y **Oscuro**. La elección se guarda para la
próxima vez que abras la aplicación.

### Limpiar

**Limpiar** borra la búsqueda, la tabla y el dashboard.

---

## 5. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| La barra inferior dice `Falta` en alguna base | La app se abrió desde otra carpeta, o falta `migracion/` | Abre la consola **en la carpeta del proyecto** y ejecuta `main.py` desde ahí. Si `migracion/` no existe, vuelve a correr `setup_db_.py`. |
| `setup_db_.py` no encuentra el `.zip` | El archivo no está en Descargas | Muévelo a Descargas, o ejecuta `setup_db_.py --zip /ruta/al/archivo.zip`. |
| `setup_db_.py` dice "El .zip no contiene: ..." | La descarga está incompleta o el comprimido no corresponde | Vuelve a descargar el archivo de datos de prueba. |
| `ModuleNotFoundError: No module named 'PySide6'` (o `pandas`, `openpyxl`) | El entorno virtual no está activo | Actívalo (paso 3.2) y repite `pip install -r requirements.txt`. |
| `pip` no instala `pandas==3.0.3` | La versión de Python es menor a 3.11 | Instala Python 3.11 o superior y vuelve a crear el entorno virtual. |
| "El archivo Excel no tiene la columna 'OP'" al cargar el lote | El Excel no tiene un encabezado `OP` | Renombra la columna a `OP`; no importan mayúsculas ni espacios. |
| `python3: command not found` (macOS) | Python no está instalado | Instálalo desde python.org o con `brew install python`. |

---

## 6. Estructura del proyecto

| Archivo | Rol |
|---|---|
| `main.py` | Ventana principal, pestaña Resumen, ventana de detalle y exportación |
| `dashboard.py` | Pestaña Dashboard: indicadores y gráficos (QtCharts) |
| `themes.py` | Temas claro y oscuro, y el selector de tema |
| `database.py` | Consultas a las tres bases SQLite |
| `service.py` | Lectura del Excel de lote y utilidades |
| `config.py` | Ruta de datos (`migracion/`), nombres de las bases y columnas |
| `setup_db_.py` | Prepara la carpeta `migracion/` desde el `.zip` de Descargas |
| `requirements.txt` | Dependencias de Python |
