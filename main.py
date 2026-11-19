import sys
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QStatusBar, QMessageBox, QHeaderView, QGroupBox, QCheckBox,
    QFileDialog, QAbstractItemView, QDialog, QComboBox
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import themes
from database import DatabaseManager
from config import Config
from service import ExcelService, to_float
from pathlib import Path
from itertools import groupby

# =====================================================================
# UTILIDADES DE TABLA
# =====================================================================
NUM_ROLE = Qt.ItemDataRole.UserRole  # Guarda el valor numérico real (para ordenar y exportar)


class NumericItem(QTableWidgetItem):
    """Celda numérica: muestra el valor con miles y decimales, alineado a la derecha,
    y ordena/exporta por el valor real (no por el texto formateado)."""

    def __init__(self, value, decimals=2):
        num = None if value is None or str(value).strip() == "" else to_float(value)
        super().__init__("" if num is None else f"{num:,.{decimals}f}")
        self.setData(NUM_ROLE, num)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        a, b = self.data(NUM_ROLE), other.data(NUM_ROLE)
        if a is None or b is None:
            return super().__lt__(other)
        return a < b


def crear_item(col, value):
    """Devuelve una celda numérica si la columna está en Config.NUMERIC_FORMATS, si no una de texto."""
    if col in Config.NUMERIC_FORMATS:
        return NumericItem(value, Config.NUMERIC_FORMATS[col])
    return QTableWidgetItem("" if value is None else str(value).strip())


def tabla_a_df(tabla):
    """Convierte un QTableWidget a DataFrame usando el valor numérico real cuando existe."""
    columnas = tabla.columnCount()
    headers = [tabla.horizontalHeaderItem(c).text() for c in range(columnas)]

    datos = []
    for r in range(tabla.rowCount()):
        fila_data = []
        for c in range(columnas):
            item = tabla.item(r, c)
            num = item.data(NUM_ROLE) if item else None
            if num is not None:
                valor = num
            else:
                valor = item.text() if item else ""
                try:
                    num = float(valor)
                    valor = int(num) if num.is_integer() else num
                except ValueError:
                    pass
            fila_data.append(valor)
        datos.append(fila_data)

    return pd.DataFrame(datos, columns=headers)


# =====================================================================
# NUEVA VENTANA: DetalleWindow (Vista Master-Detail)
# =====================================================================
class DetalleWindow(QDialog):
    def __init__(self, op, categoria, db_manager, parent=None):
        super().__init__(parent)
        self.op = op
        self.categoria_original = str(categoria).strip()  # Guardamos el texto exacto de la DB
        self.categoria_lower = self.categoria_original.lower() # S
        self.db_manager = db_manager
        
        self.setWindowTitle(f"Detalle de OP: {self.op} - {categoria.capitalize()}")
        self.resize(1000, 500)
        
        # Elimina la ventana de la memoria cuando se cierra
        self.setAttribute(Qt.WA_DeleteOnClose) 
        
        self._build_ui()
        self.cargar_datos()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.tabla_detalle = QTableWidget(0, 0)
        self.tabla_detalle.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_detalle.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_detalle.setAlternatingRowColors(True)
        self.tabla_detalle.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tabla_detalle.horizontalHeader().setStretchLastSection(True)
        self.tabla_detalle.setSortingEnabled(True)
        layout.addWidget(self.tabla_detalle)

        # Pie de totales: fijo debajo de la tabla, no se mueve al ordenar
        self.total_label = QLabel("")
        self.total_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_label.setObjectName("totalLabel")  # Colores según tema (themes.py)
        layout.addWidget(self.total_label)
        self._totales = {}

        btn_layout = QHBoxLayout()
        
        self.btn_exportar = QPushButton("📊 Exportar a Excel")
        self.btn_exportar.setCursor(Qt.PointingHandCursor)
        self.btn_exportar.setObjectName("btnExportar")
        self.btn_exportar.clicked.connect(self.exportar_excel_detalle)
        
        # Alineamos el botón a la derecha
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_exportar)
        
        layout.addLayout(btn_layout)

    def cargar_datos(self):
        # Definimos las categorías exactas en minúsculas según el cuadro
        categorias_hilado = [
            "compra de hilado",
            "envio de hilado a tintorería",
            "servicio teñido de hilado",
            "hilado enviado a tejeduría",
            "servicio de reenconado",  # Servicio sobre hilado: se registra en mov_hilado
            "hilado sin valor comercial",
            "hilado transferencia multitech"
        ]
        categorias_merma_hilado = [
            "hilado merma de tejeduría",
            "hilado consumido en tejeduría",
        ]
        categorias_tela = [
            "compra de tela",
            "envio de tela a tintorería",
            "servicio de tejeduría - tela principal",
            "servicio de tejeduría",
            "servicio de tintorería",
            "servicio de post-teñido",
            "servicio de post-teñido (estampado-sublimado)",
            "envio de tela a cmt",
            "transferencia de partidas"
        ]

        # Limpiamos espacios en blanco extremos por seguridad
        cat_limpia = self.categoria_lower.strip()

        # Clasificación exacta basada en las listas
        if cat_limpia in categorias_hilado:
            schema, table, headers = "main", "mov_hilado", Config.HILADO_HEADERS
        elif cat_limpia in categorias_merma_hilado:
            schema, table, headers = "main", "consumo_hilado", Config.HILADO_HEADERS
        elif cat_limpia in categorias_tela:
            schema, table, headers = "tejidos", "mov_tejeduria", Config.TEJIDO_HEADERS
        else:
            QMessageBox.warning(self, "Aviso", f"Categoría no reconocida: {self.categoria_original}")
            return

        try:
            # Pasamos la variable ORIGINAL a la base de datos
            rows = self.db_manager.fetch_data_categoria(
                schema, table, headers, [self.op], self.categoria_original, order_col="fecha"
            )
            self._llenar_tabla(headers, rows)
        except Exception as e:
            QMessageBox.critical(self, "Error de consulta", f"No se pudo cargar el detalle:\n{str(e)}")

    def _llenar_tabla(self, headers, rows):
        self.tabla_detalle.setSortingEnabled(False)
        self.tabla_detalle.setColumnCount(len(headers))
        self.tabla_detalle.setRowCount(len(rows))
        self.tabla_detalle.setHorizontalHeaderLabels([label for _, label in headers])

        cols = [c for c, _ in headers]
        kgs_idx = cols.index("kgs") if "kgs" in cols else None
        usd_idx = cols.index("dolares") if "dolares" in cols else None

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = crear_item(cols[c], value)

                if kgs_idx is not None and c == kgs_idx:
                    fval = to_float(value)
                    if fval < 0:
                        item.setData(themes.ROLE_ESTILO, "negativo")
                    elif fval > 0:
                        item.setData(themes.ROLE_ESTILO, "positivo")

                self.tabla_detalle.setItem(r, c, item)

        themes.recolorear_tabla(self.tabla_detalle)
        self.tabla_detalle.resizeColumnsToContents()
        self.tabla_detalle.setSortingEnabled(True)
        self._actualizar_totales(headers, rows, kgs_idx, usd_idx)

    def _actualizar_totales(self, headers, rows, kgs_idx, usd_idx):
        """Calcula y muestra el pie de totales (debe cuadrar con la fila del resumen)."""
        total_kg = sum(to_float(r[kgs_idx]) for r in rows) if kgs_idx is not None else 0.0
        total_usd = sum(to_float(r[usd_idx]) for r in rows) if usd_idx is not None else 0.0
        cu = total_usd / total_kg if total_kg else None

        self._totales = {}
        if kgs_idx is not None:
            self._totales[headers[kgs_idx][1]] = round(total_kg, 2)
        if usd_idx is not None:
            self._totales[headers[usd_idx][1]] = round(total_usd, 2)

        cu_txt = f"{cu:,.2f}" if cu is not None else "-"
        self.total_label.setText(
            f"TOTAL  |  Movimientos: {len(rows):,}  |  Kg: {total_kg:,.2f}  |  "
            f"US$: {total_usd:,.2f}  |  C.U. ponderado US$: {cu_txt}"
        )
    
    def exportar_excel_detalle(self):
        if self.tabla_detalle.rowCount() == 0:
            QMessageBox.warning(self, "Sin datos", "No hay registros para exportar.")
            return

        # 1. Obtener la ruta de "Descargas" del usuario actual de forma universal
        descargas_dir = Path.home() / "Downloads"
        
        # 2. Generar un nombre por defecto limpio
        nombre_cat = self.categoria_original.replace(" ", "_").replace("/", "-")
        default_filename = f"Detalle_OP_{self.op}_{nombre_cat}.xlsx"
        default_path = str(descargas_dir / default_filename)

        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte de detalle", default_path, "Excel (*.xlsx)"
        )

        if not ruta_archivo:
            return

        try:
            df = tabla_a_df(self.tabla_detalle)
            if self._totales:
                fila_total = {df.columns[0]: "TOTAL", **self._totales}
                df = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)
            with pd.ExcelWriter(ruta_archivo, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Detalle', index=False)
            
            QMessageBox.information(self, "Éxito", "Archivo exportado correctamente en:\n" + ruta_archivo)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al exportar:\n{str(e)}")


# =====================================================================
# VENTANA PRINCIPAL
# =====================================================================
class TrazabilidadWindow(QMainWindow):
    def __init__(self, db_dir):
        super().__init__()
        self.db_manager = DatabaseManager(db_dir)
        self.ops_lote = []
        
        self.setWindowTitle("Resumen General de OPs")
        self.resize(1000, 600)
        self._build_ui()
        self._update_status()
        self.setWindowIcon(QIcon("logo/inspeccion.png"))

    # --- UI Setup ---
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self._build_search_box(main_layout)
        
        self.resumen_label = QLabel("")
        self.resumen_label.setWordWrap(True)
        self.resumen_label.setFont(QFont("Arial", 10, QFont.Bold))
        main_layout.addWidget(self.resumen_label)

        # Ahora solo construimos la tabla de resumen general
        self._build_resumen_table(main_layout)
        
        self.setStatusBar(QStatusBar())
        self._build_selector_tema()

    def _build_selector_tema(self):
        """Selector de tema fijo a la derecha de la barra de estado (no se borra con Limpiar)."""
        self.cmb_tema = QComboBox()
        self.cmb_tema.addItems(list(themes.OPCIONES.keys()))
        actual = next(k for k, v in themes.OPCIONES.items() if v == themes.preferencia())
        self.cmb_tema.setCurrentText(actual)
        self.cmb_tema.setToolTip("Sistema: sigue el modo claro/oscuro de Windows")
        self.cmb_tema.currentTextChanged.connect(
            lambda texto: themes.aplicar_tema(QApplication.instance(), themes.OPCIONES[texto], guardar=True)
        )
        self.statusBar().addPermanentWidget(QLabel("Tema:"))
        self.statusBar().addPermanentWidget(self.cmb_tema)

    def _build_search_box(self, parent_layout):
        search_box = QGroupBox("Búsqueda")
        search_layout = QHBoxLayout(search_box)

        search_layout.addWidget(QLabel("OP Referencial:"))
        self.op_input = QLineEdit()
        self.op_input.setPlaceholderText("Ej: 15480")
        self.op_input.setMaximumWidth(220)
        self.op_input.returnPressed.connect(self.buscar)
        search_layout.addWidget(self.op_input)

        self.chk_lote = QCheckBox("Por lote (Excel)")
        self.chk_lote.toggled.connect(self._toggle_lote)
        search_layout.addWidget(self.chk_lote)
        
        self.btn_cargar_excel = QPushButton("📁 Cargar Excel")
        self.btn_cargar_excel.setEnabled(False)
        self.btn_cargar_excel.clicked.connect(self.cargar_excel_ops)
        search_layout.addWidget(self.btn_cargar_excel)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar)
        search_layout.addWidget(self.btn_buscar)

        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.clicked.connect(self.limpiar)
        search_layout.addWidget(self.btn_limpiar)

        search_layout.addStretch()

        self.btn_exportar = QPushButton("📊 Exportar a Excel")
        self.btn_exportar.clicked.connect(self.exportar_excel)
        self.btn_exportar.setObjectName("btnExportar")
        search_layout.addWidget(self.btn_exportar)

        parent_layout.addWidget(search_box)

    def _build_resumen_table(self, parent_layout):
        # N columnas originales + 1 columna para el botón "Acción"
        n_cols = len(Config.RESUMEN_HEADERS) + 1 
        self.tabla_resumen = QTableWidget(0, n_cols)
        self.tabla_resumen.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_resumen.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_resumen.setAlternatingRowColors(True)
        self.tabla_resumen.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tabla_resumen.horizontalHeader().setStretchLastSection(True)
        # El orden del resumen es de negocio (OP -> flujo productivo) y contiene filas de
        # subtotal, por eso no se permite reordenar con clic en el encabezado.
        self.tabla_resumen.setSortingEnabled(False)
        parent_layout.addWidget(self.tabla_resumen)

    # --- Acciones UI ---
    def _update_status(self):
        h_ok, t_ok, r_ok= self.db_manager.check_health()
        t_r = "OK" if r_ok else "Falta"
        t_h = "OK" if h_ok else "Falta"
        t_t = "OK" if t_ok else "Falta"
        self.statusBar().showMessage(f"Datos cargados: Hilado: [{t_h}] | Tejidos: [{t_t}] | Resumen: [{t_r}]")

    def _toggle_lote(self, checked):
        self.op_input.setEnabled(not checked)
        self.btn_cargar_excel.setEnabled(checked)
        self.op_input.clear()
        
        if checked:
            self.op_input.setPlaceholderText("Modo lote: Carga un archivo Excel ->")
            self.btn_buscar.setText("Buscar Lote")
        else:
            self.op_input.setPlaceholderText("Ej: 15480")
            self.btn_buscar.setText("Buscar")
            self.ops_lote = []

    def limpiar(self):
        self.op_input.clear()
        self.tabla_resumen.setRowCount(0)
        self.statusBar().showMessage("")
        self.resumen_label.setText("")
        self.op_input.setFocus()

    def cargar_excel_ops(self):
        ruta_archivo, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Excel con lista de OPs", "", "Archivos Excel (*.xlsx *.xls);;Todos (*.*)"
        )
        if not ruta_archivo:
            return

        try:
            self.ops_lote = ExcelService.load_ops_from_excel(ruta_archivo)
            if not self.ops_lote:
                QMessageBox.warning(self, "Excel vacío", "La columna 'OP' no contiene datos válidos.")
                return

            self.op_input.setText(f"Lote listo {len(self.ops_lote)} OPs cargadas")
            self.statusBar().showMessage(f"✅ Excel leído. {len(self.ops_lote)} OPs listas para procesar.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo leer el archivo Excel:\n{str(e)}")

    def buscar(self):
        if self.chk_lote.isChecked():
            if not self.ops_lote:
                QMessageBox.information(self, "Falta Excel", "Carga un archivo Excel primero.")
                return
            lista_ops = self.ops_lote
            op_text_resumen = f"Lote ({len(lista_ops)} OPs)"
        else:
            op_text = self.op_input.text().strip()
            if not op_text:
                QMessageBox.information(self, "Falta OP", "Ingresa un número de OP Referencial.")
                return
            lista_ops = [op_text]
            op_text_resumen = f"OP {op_text}"

        h_ok, t_ok, r_ok = self.db_manager.check_health()
        if not h_ok or not t_ok or not r_ok:
            QMessageBox.critical(self, "Error", "Faltan bases de datos en la ruta especificada.")
            return

        try:
            resumen_rows = self.db_manager.fetch_data("resumen", "resumen_op", Config.RESUMEN_HEADERS, lista_ops)
        except Exception as e:
            QMessageBox.critical(self, "Error de consulta", str(e))
            return
        
        # 1. Definimos el orden exacto en una lista (en minúsculas para estandarizar)
        orden_categorias = [
            "compra de hilado",
            "envio de hilado a tintorería",
            "servicio teñido de hilado",
            "hilado enviado a tejeduría",
            "hilado merma de tejeduría",
            "hilado consumido en tejeduría",
            "servicio de tejeduría - tela principal",
            "servicio de tejeduría",
            "envio de tela a tintorería",
            "servicio de tintorería",
            "compra de tela",
            "servicio de reenconado",
            "servicio de post-teñido",
            "servicio de post-teñido (estampado-sublimado)",
            "envio de tela a cmt",
            "transferencia de partidas",
            "hilado sin valor comercial",
            "hilado transferencia multitech"
        ]
        
        # 2. Creamos un diccionario para asignar un "peso" numérico a cada categoría
        mapa_orden = {cat: index for index, cat in enumerate(orden_categorias)}

        # 3. Posición de cada OP según el orden de ingreso (Excel o campo de texto)
        mapa_op = {str(op).strip(): i for i, op in enumerate(lista_ops)}

        # 4. Ordenamos primero por OP y luego por el flujo productivo de la categoría.
        #    Categorías no mapeadas reciben 999 y van al final de su OP.
        def sort_key(row):
            op = str(row[0]).strip()
            cat = str(row[1]).strip().lower()
            return (mapa_op.get(op, len(mapa_op)), op, mapa_orden.get(cat, 999))

        resumen_rows = sorted(resumen_rows, key=sort_key)

        self._llenar_tabla_resumen(Config.RESUMEN_HEADERS, resumen_rows)
        n_ops = len({str(row[0]).strip() for row in resumen_rows})
        self.resumen_label.setText(
            f"Búsqueda: {op_text_resumen} | OPs con datos: {n_ops} | Registros: {len(resumen_rows)}"
        )

    def _llenar_tabla_resumen(self, headers, rows):
        """Llena el resumen agrupado por OP (las filas deben venir ordenadas por OP), con una
        fila de subtotal por OP y un total general en lote. Devuelve la cantidad de OPs."""
        cols = [c for c, _ in headers]
        op_idx = cols.index("op") if "op" in cols else 0
        cat_idx = cols.index("categoria") if "categoria" in cols else 1
        val_idx = cols.index("valorizado_total")

        # Armamos la lista de filas a pintar: datos + subtotal por OP + total general
        filas = []
        for op, grupo in groupby(rows, key=lambda row: str(row[op_idx]).strip()):
            grupo = list(grupo)
            filas.extend(("dato", row) for row in grupo)
            #subtotal = sum(to_float(row[val_idx]) for row in grupo)
            #filas.append(("subtotal", f"Subtotal OP {op}", subtotal))

        #n_ops = sum(1 for f in filas if f[0] == "subtotal")
        #if n_ops == 1:
        #    _, etiqueta, valor = filas[-1]
        #    filas[-1] = ("total", etiqueta.replace("Subtotal", "TOTAL"), valor)
        #elif n_ops > 1:
        #    total = sum(f[2] for f in filas if f[0] == "subtotal")
        #    filas.append(("total", f"TOTAL LOTE ({n_ops} OPs)", total))

        self.tabla_resumen.clearSpans()
        self.tabla_resumen.setRowCount(0)  # Limpia también los botones de la búsqueda anterior
        self.tabla_resumen.setRowCount(len(filas))

        # Preparamos las etiquetas añadiendo "Acción" al final
        labels = [label for _, label in headers] + ["Acción"]
        self.tabla_resumen.setColumnCount(len(labels))
        self.tabla_resumen.setHorizontalHeaderLabels(labels)

        for r, fila in enumerate(filas):
            if fila[0] == "dato":
                self._pintar_fila_dato(r, cols, fila[1], op_idx, cat_idx)
            else:
                self._pintar_fila_total(r, cols, *fila)

        self.tabla_resumen.resizeColumnsToContents()
        #return n_ops

    def _pintar_fila_total(self, r, cols, tipo, etiqueta, valor):
        """Fila de subtotal/total: solo suma el valorizado (los kg mezclan hilado, tela y servicios)."""
        fuente = QFont()
        fuente.setBold(True)
        ayuda = ("Suma con signo de las categorías (entradas − envíos).\n"
                 "Los kg no se suman porque mezclan hilado, tela y servicios.")

        for c in range(len(cols) + 1):  # +1 = columna "Acción"
            if c == 0:
                item = QTableWidgetItem(etiqueta)
            elif c < len(cols) and cols[c] == "valorizado_total":
                item = NumericItem(valor, Config.NUMERIC_FORMATS["valorizado_total"])
            else:
                item = QTableWidgetItem("")
            item.setData(themes.ROLE_ESTILO, tipo)  # "subtotal" | "total": colores según tema
            item.setFont(fuente)
            item.setToolTip(ayuda)
            self.tabla_resumen.setItem(r, c, item)

        self.tabla_resumen.setSpan(r, 0, 1, 2)  # La etiqueta ocupa OP + Categoría
        themes.recolorear_tabla(self.tabla_resumen)

    def _pintar_fila_dato(self, r, cols, row, op_idx, cat_idx):
        for c, value in enumerate(row):
            self.tabla_resumen.setItem(r, c, crear_item(cols[c], value))

        # --- AGREGAR EL BOTÓN AL FINAL DE LA FILA ---
        op_val = str(row[op_idx])
        cat_val = str(row[cat_idx])

        btn_detalle = QPushButton("🔍 Ver Detalle")
        btn_detalle.setCursor(Qt.PointingHandCursor)
        btn_detalle.setObjectName("btnDetalle")  # Colores según tema (themes.py)

        # Usamos lambda con parámetros por defecto para capturar correctamente los valores del bucle
        btn_detalle.clicked.connect(lambda checked=False, o=op_val, c=cat_val: self.abrir_detalle(o, c))
        
        # Insertamos el botón en la última columna de la fila
        self.tabla_resumen.setCellWidget(r, len(row), btn_detalle)

    def abrir_detalle(self, op, categoria):
        """Instancia y muestra la ventana de detalle para la OP y categoría especificadas."""
        self.ventana_detalle = DetalleWindow(op, categoria, self.db_manager, self)
        self.ventana_detalle.show()

    def exportar_excel(self):
        if self.tabla_resumen.rowCount() == 0:
            QMessageBox.warning(self, "Sin datos", "No hay registros para exportar.")
            return

        op_actual = self.op_input.text().strip() or "General"
        descargas_dir = Path.home() / "Downloads"
        default_filename = f"Resumen_OP_{op_actual}.xlsx"
        default_path = str(descargas_dir / default_filename)
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte", default_path, "Excel (*.xlsx)"
        )

        if not ruta_archivo:
            return

        try:
            df_resumen = tabla_a_df(self.tabla_resumen)
            # Removemos la última columna ("Acción") ya que contiene los widgets de los botones
            if "Acción" in df_resumen.columns:
                df_resumen = df_resumen.drop(columns=["Acción"])
                
            with pd.ExcelWriter(ruta_archivo, engine='openpyxl') as writer:
                df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            self.statusBar().showMessage(f"✅ Reporte guardado: {ruta_archivo}")
            QMessageBox.information(self, "Éxito", "Archivo exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al exportar:\n{str(e)}")

# =====================================================================
# EJECUCIÓN DEL SCRIPT
# =====================================================================
def main():
    db_dir = sys.argv[1] if len(sys.argv) > 1 else Config.DEFAULT_DIR
    app = QApplication(sys.argv)
    themes.aplicar_tema(app)               # Tema guardado del usuario (por defecto: Sistema)
    themes.seguir_cambios_del_sistema(app)
    window = TrazabilidadWindow(db_dir)
    window.show()
    sys.exit(app.exec())

    #db_manager =DatabaseManager(Config.DEFAULT_DIR)
    #(hilado,tejido,resumen) =db_manager.get_paths()
    #print("ruta hilado: ",hilado)
    #print("ruta tela: ",tejido)
    #print("ruta resumen: ",resumen)

if __name__ == "__main__":
    main()