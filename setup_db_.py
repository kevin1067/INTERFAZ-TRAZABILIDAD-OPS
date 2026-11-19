"""
Prepara las bases de datos de prueba del proyecto.

1. Busca el comprimido de datos (por defecto `migracion.zip`) en la carpeta Descargas.
2. Crea la carpeta `migracion/` dentro del proyecto.
3. Descomprime ahí las tres bases SQLite.

Solo usa la librería estándar de Python: se puede ejecutar antes de instalar requirements.txt.

Uso:
    python3 setup_db_.py          (macOS)
    python  setup_db_.py          (Windows)

Opciones (ver `python setup_db_.py --help`):
    --zip RUTA        usar un .zip específico en lugar de buscarlo en Descargas
    --descargas DIR   buscar el .zip en otra carpeta
    --destino DIR     descomprimir en otra carpeta (por defecto: <proyecto>/migracion)
    --force           reemplazar las bases existentes sin preguntar
"""
import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent
sys.path.insert(0, str(PROYECTO))  # Permite importar config.py aunque se ejecute desde otra carpeta
from config import Config  # noqa: E402  (config.py solo usa pathlib: librería estándar)

NOMBRE_ZIP = "migracion.zip"
BASES = [Config.DB_HILADO, Config.DB_TEJIDOS, Config.DB_RESUMEN]
CABECERA_SQLITE = b"SQLite format 3\x00"


class SetupError(Exception):
    """Error esperado: se muestra al usuario sin traceback."""


# ---------------------------------------------------------------- búsqueda
def carpeta_descargas():
    """Carpeta Descargas del usuario. En macOS y Windows la carpeta real se llama
    'Downloads' aunque el sistema esté en español."""
    return Path.home() / "Downloads"


def miembros_db(zf):
    """Devuelve {nombre_base: miembro_del_zip} para las bases requeridas.

    Acepta las bases en la raíz del .zip o dentro de una subcarpeta (ej. 'migracion/').
    Ignora los archivos basura que agrega macOS al comprimir ('__MACOSX/', '._archivo').
    """
    encontrados = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        partes = Path(info.filename).parts
        nombre = partes[-1] if partes else ""
        if "__MACOSX" in partes or nombre.startswith("._"):
            continue
        if nombre in BASES and nombre not in encontrados:
            encontrados[nombre] = info
    return encontrados


def es_zip_de_datos(ruta):
    try:
        with zipfile.ZipFile(ruta) as zf:
            return len(miembros_db(zf)) == len(BASES)
    except (zipfile.BadZipFile, OSError):
        return False


def buscar_zip(descargas):
    """Busca primero 'migracion.zip'. Si no está (ej. el navegador lo guardó como
    'migracion (1).zip'), usa el .zip más reciente de la carpeta que contenga las tres bases."""
    if not descargas.is_dir():
        raise SetupError(f"No existe la carpeta de descargas: {descargas}")

    exacto = descargas / NOMBRE_ZIP
    if exacto.is_file():
        return exacto

    candidatos = sorted(
        (p for p in descargas.glob("*.zip") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for zip_path in candidatos:
        if es_zip_de_datos(zip_path):
            return zip_path

    raise SetupError(
        f"No se encontró '{NOMBRE_ZIP}' en {descargas}\n"
        f"  (tampoco otro .zip que contenga {', '.join(BASES)}).\n"
        "  Descarga el archivo de datos de prueba a esa carpeta y vuelve a ejecutar el script,\n"
        "  o indica la ruta directamente:  python setup_db_.py --zip /ruta/al/archivo.zip"
    )


# ----------------------------------------------------------- descompresión
def confirmar_reemplazo(destino, force):
    existentes = [b for b in BASES if (destino / b).exists()]
    if not existentes or force:
        return True
    print(f"\nLa carpeta {destino} ya contiene: {', '.join(existentes)}")
    try:
        respuesta = input("¿Reemplazarlas con los datos del .zip? [s/N]: ").strip().lower()
    except EOFError:
        respuesta = ""
    return respuesta in ("s", "si", "sí", "y", "yes")


def descomprimir(zip_path, destino):
    """Extrae las bases a una carpeta temporal, las valida y recién entonces las copia al
    destino, para no dejar la carpeta a medio llenar si algo falla."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise SetupError(f"El archivo no es un .zip válido o está dañado: {zip_path}")

    with zf, tempfile.TemporaryDirectory() as tmp:
        miembros = miembros_db(zf)
        faltantes = [b for b in BASES if b not in miembros]
        if faltantes:
            raise SetupError(
                f"El .zip no contiene: {', '.join(faltantes)}\n"
                f"  Archivo revisado: {zip_path}"
            )

        tmp = Path(tmp)
        for nombre, info in miembros.items():
            # Se escribe por nombre de archivo (no por la ruta interna del .zip) para que
            # ninguna entrada pueda salir de la carpeta temporal.
            with zf.open(info) as origen, open(tmp / nombre, "wb") as salida:
                shutil.copyfileobj(origen, salida)
            with open(tmp / nombre, "rb") as f:
                if f.read(len(CABECERA_SQLITE)) != CABECERA_SQLITE:
                    raise SetupError(f"'{nombre}' dentro del .zip no es una base SQLite válida.")

        destino.mkdir(parents=True, exist_ok=True)
        for nombre in BASES:
            shutil.copy2(tmp / nombre, destino / nombre)


# ---------------------------------------------------------------- principal
def main(argv=None):
    # Consolas antiguas de Windows (cp1252): un carácter no representable no debe romper el script
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Descomprime los datos de prueba en la carpeta 'migracion' del proyecto."
    )
    parser.add_argument("--zip", type=Path, help="Ruta a un .zip específico.")
    parser.add_argument("--descargas", type=Path, default=carpeta_descargas(),
                        help="Carpeta donde buscar el .zip (por defecto: Descargas del usuario).")
    parser.add_argument("--destino", type=Path, default=PROYECTO / Config.DEFAULT_DIR,
                        help="Carpeta de destino (por defecto: <proyecto>/migracion).")
    parser.add_argument("--force", action="store_true",
                        help="Reemplazar las bases existentes sin preguntar.")
    args = parser.parse_args(argv)

    try:
        if args.zip:
            zip_path = args.zip.expanduser().resolve()
            if not zip_path.is_file():
                raise SetupError(f"No existe el archivo: {zip_path}")
        else:
            print(f"Buscando '{NOMBRE_ZIP}' en: {args.descargas}")
            zip_path = buscar_zip(args.descargas.expanduser())
        print(f"Archivo encontrado: {zip_path}")

        destino = args.destino.expanduser().resolve()
        if not confirmar_reemplazo(destino, args.force):
            print("Operación cancelada. No se modificó nada.")
            return 1

        descomprimir(zip_path, destino)
    except SetupError as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        return 1

    print(f"\nBases de datos listas en: {destino}")
    for nombre in BASES:
        tamano_mb = (destino / nombre).stat().st_size / 1_048_576
        print(f"  [OK] {nombre:<20} {tamano_mb:6.1f} MB")
    print("\nSiguiente paso: instalar las dependencias y abrir la aplicación (ver README.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
