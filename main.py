import sys
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QStatusBar, QMessageBox, QHeaderView, QGroupBox, QCheckBox,
    QFileDialog, QAbstractItemView, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from database import DatabaseManager
from config import Config
from service import ExcelService, to_float
from pathlib import Path

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
        self.tabla_detalle.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #E2ECF8;
                color: #000000;
            }
        """)
        layout.addWidget(self.tabla_detalle)
        btn_layout = QHBoxLayout()
        
        self.btn_exportar = QPushButton("📊 Exportar a Excel")
        self.btn_exportar.setCursor(Qt.PointingHandCursor)
        self.btn_exportar.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32; 
                color: white; 
                font-weight: bold; 
                padding: 6px 16px; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:pressed { background-color: #1B5E20; }
        """)
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
            "servicio de tejeduría",
            "servicio de tintorería",
            "servicio de reenconado",
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

        kgs_idx = next((i for i, (c, _) in enumerate(headers) if c == "kgs"), None)

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                display = "" if value is None else str(value).strip()
                item = QTableWidgetItem(display)
                
                if kgs_idx is not None and c == kgs_idx:
                    fval = to_float(value)
                    if fval < 0:
                        item.setForeground(QColor("#FF5858"))
                    elif fval > 0:
                        item.setForeground(QColor("#65DF6B"))
                        
                self.tabla_detalle.setItem(r, c, item)

        self.tabla_detalle.resizeColumnsToContents()
        self.tabla_detalle.setSortingEnabled(True)
    
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
            df = self._tabla_a_df(self.tabla_detalle)
            with pd.ExcelWriter(ruta_archivo, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Detalle', index=False)
            
            QMessageBox.information(self, "Éxito", "Archivo exportado correctamente en:\n" + ruta_archivo)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al exportar:\n{str(e)}")

    def _tabla_a_df(self, tabla):
        filas = tabla.rowCount()
        columnas = tabla.columnCount()
        headers = [tabla.horizontalHeaderItem(c).text() for c in range(columnas)]
        
        datos = []
        for r in range(filas):
            fila_data = []
            for c in range(columnas):
                item = tabla.item(r, c)
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
        self.btn_exportar.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
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
        self.tabla_resumen.setSortingEnabled(True)
        self.tabla_resumen.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #E2ECF8;
                color: #000000;
            }
        """)
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
            "servicio de tejeduría",
            "envio de tela a tintorería",
            "servicio de tintorería",
            "compra de tela",
            "servicio de reenconado",
            "servicio de post-teñido",
            "servicio de post-teñido (estampado-sublimado)",
            "envio de tela a CMT",
            "transferencia de partidas",
            "hilado sin valor comercial",
            "hilado transferencia multitech"
        ]
        
        # 2. Creamos un diccionario para asignar un "peso" numérico a cada categoría
        mapa_orden = {cat: index for index, cat in enumerate(orden_categorias)}

        # 3. Función clave para ordenar las filas
        def sort_key(row):
            # Según tu Config.RESUMEN_HEADERS, la categoría está en el índice 1 de la tupla devuelta
            cat = str(row[1]).strip().lower() 
            # Si la categoría está en nuestra lista, le asigna su posición.
            # Si en el futuro aparece una nueva no mapeada, le asigna 999 para enviarla al final.
            return mapa_orden.get(cat, 999) 

        # 4. Ordenamos la lista de resultados usando la función clave
        resumen_rows = sorted(resumen_rows, key=sort_key)

        self._llenar_tabla_resumen(Config.RESUMEN_HEADERS, resumen_rows)
        self.resumen_label.setText(f"Búsqueda: {op_text_resumen} | Resultados: {len(resumen_rows)} categorías")

    def _llenar_tabla_resumen(self, headers, rows):
        self.tabla_resumen.setSortingEnabled(False)
        self.tabla_resumen.setRowCount(len(rows))
        
        # Preparamos las etiquetas añadiendo "Acción" al final
        labels = [label for _, label in headers] + ["Acción"]
        self.tabla_resumen.setColumnCount(len(labels))
        self.tabla_resumen.setHorizontalHeaderLabels(labels)

        # Buscar el índice de las columnas clave para pasarlas al botón
        op_idx = next((i for i, (c, _) in enumerate(headers) if c == "op"), 0)
        cat_idx = next((i for i, (c, _) in enumerate(headers) if c == "categoria"), 1)

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                display = "" if value is None else str(value).strip()
                item = QTableWidgetItem(display)
                self.tabla_resumen.setItem(r, c, item)
            
            # --- AGREGAR EL BOTÓN AL FINAL DE LA FILA ---
            op_val = str(row[op_idx])
            cat_val = str(row[cat_idx])
            
            btn_detalle = QPushButton("🔍 Ver Detalle")
            btn_detalle.setCursor(Qt.PointingHandCursor)
            btn_detalle.setStyleSheet("""
                QPushButton {
                    background-color: #2B2D30;      /* Fondo gris oscuro */
                    color: #DFE1E5;                 /* Texto gris claro/blanco */
                    border: 1px solid #43454A;      /* Borde sutil */
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #35373C;      /* Se aclara sutilmente al pasar el cursor */
                    color: #FFFFFF;                 /* Texto blanco brillante */
                    border: 1px solid #5E6168;      /* Borde más visible */
                }
                QPushButton:pressed {
                    background-color: #1E1F22;      /* Se oscurece al hacer clic */
                    color: #9DA0A8;                 /* Texto más opaco */
                }
            """)
            
            # Usamos lambda con parámetros por defecto para capturar correctamente los valores del bucle
            btn_detalle.clicked.connect(lambda checked=False, o=op_val, c=cat_val: self.abrir_detalle(o, c))
            
            # Insertamos el botón en la última columna de la fila
            self.tabla_resumen.setCellWidget(r, len(row), btn_detalle)

        self.tabla_resumen.resizeColumnsToContents()
        self.tabla_resumen.setSortingEnabled(True)

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
            df_resumen = self._tabla_a_df(self.tabla_resumen)
            # Removemos la última columna ("Acción") ya que contiene los widgets de los botones
            if "Acción" in df_resumen.columns:
                df_resumen = df_resumen.drop(columns=["Acción"])
                
            with pd.ExcelWriter(ruta_archivo, engine='openpyxl') as writer:
                df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            self.statusBar().showMessage(f"✅ Reporte guardado: {ruta_archivo}")
            QMessageBox.information(self, "Éxito", "Archivo exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al exportar:\n{str(e)}")

    def _tabla_a_df(self, tabla):
        filas = tabla.rowCount()
        columnas = tabla.columnCount()
        headers = [tabla.horizontalHeaderItem(c).text() for c in range(columnas)]
        
        datos = []
        for r in range(filas):
            fila_data = []
            for c in range(columnas):
                item = tabla.item(r, c)
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
# EJECUCIÓN DEL SCRIPT
# =====================================================================
def main():
    db_dir = sys.argv[1] if len(sys.argv) > 1 else Config.DEFAULT_DIR
    app = QApplication(sys.argv)
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