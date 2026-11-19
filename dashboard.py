"""
Pestaña Dashboard: indicadores y gráficos de la búsqueda actual (OP individual o lote).

Usa solo las filas del resumen (op, categoria, kg_netos, valorizado_total, ...),
así que siempre cuadra con la pestaña Resumen.
"""
from collections import defaultdict

from PySide6.QtCharts import (
    QBarCategoryAxis, QBarSet, QChart, QChartView, QHorizontalBarSeries,
    QHorizontalStackedBarSeries, QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QToolTip, QVBoxLayout, QWidget,
)

import themes
from service import to_float

ORDEN_CATEGORIAS = [
    "compra de hilado", "envio de hilado a tintorería", "servicio teñido de hilado",
    "hilado enviado a tejeduría", "hilado merma de tejeduría", "hilado consumido en tejeduría",
    "servicio de tejeduría - tela principal", "servicio de tejeduría", "envio de tela a tintorería",
    "servicio de tintorería", "compra de tela", "servicio de reenconado", "servicio de post-teñido",
    "servicio de post-teñido (estampado-sublimado)", "envio de tela a cmt",
    "transferencia de partidas", "hilado sin valor comercial", "hilado transferencia multitech",
]
TOP_OPS = 10


def _nombre_corto_servicio(nombre):
    """'Servicio de tintorería' -> 'Tintorería'; 'Servicio teñido de hilado' -> 'Teñido de hilado'."""
    corto = nombre
    for prefijo in ("servicio de ", "servicio "):
        if corto.lower().startswith(prefijo):
            corto = corto[len(prefijo):]
            break
    corto = corto.replace("(estampado-sublimado)", "(estamp./sublim.)")
    return corto[:1].upper() + corto[1:]


def _fmt(valor, decimales=0):
    return f"{valor:,.{decimales}f}"


class KpiTile(QFrame):
    def __init__(self, titulo, ayuda):
        super().__init__()
        self.setObjectName("kpiTile")
        self.setToolTip(ayuda)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        t = QLabel(titulo)
        t.setObjectName("kpiTitulo")
        self.valor = QLabel("-")
        self.valor.setObjectName("kpiValor")
        lay.addWidget(t)
        lay.addWidget(self.valor)

    def set_valor(self, texto):
        self.valor.setText(texto)


class DashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._build_ui()
        themes.al_cambiar_tema(self.refrescar)
        self.limpiar()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        externo.addWidget(scroll)

        contenido = QWidget()
        scroll.setWidget(contenido)
        lay = QVBoxLayout(contenido)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(12)

        self.mensaje = QLabel("")
        self.mensaje.setObjectName("notaMuted")
        self.mensaje.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.mensaje)

        # Fila de indicadores
        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        self.kpi_ops = KpiTile("OPs analizadas", "OPs de la búsqueda que tienen datos en el resumen.")
        self.kpi_servicios = KpiTile(
            "Servicios US$", "Suma de todas las categorías 'Servicio ...' (tejeduría, tintorería, teñido, etc.).")
        self.kpi_tela = KpiTile("Compra de tela US$", "Suma de la categoría 'Compra de tela'.")
        self.kpi_merma = KpiTile(
            "Merma de tejeduría", "Merma kg / (consumido kg + merma kg) de hilado en tejeduría.")
        for k in (self.kpi_ops, self.kpi_servicios, self.kpi_tela, self.kpi_merma):
            kpis.addWidget(k)
        self.panel_kpis = QWidget()
        self.panel_kpis.setLayout(kpis)
        lay.addWidget(self.panel_kpis)

        # Gráficos en grilla 2 x 2
        grilla = QGridLayout()
        grilla.setSpacing(12)
        self.vista_flujo = self._nueva_vista()
        self.vista_servicios = self._nueva_vista()
        self.vista_hilado = self._nueva_vista()
        self.vista_top = self._nueva_vista()
        grilla.addWidget(self.vista_flujo, 0, 0, 1, 2)
        grilla.addWidget(self.vista_servicios, 1, 0)
        grilla.addWidget(self.vista_hilado, 1, 1)
        grilla.addWidget(self.vista_top, 2, 0, 1, 2)
        self.panel_graficos = QWidget()
        self.panel_graficos.setLayout(grilla)
        lay.addWidget(self.panel_graficos)

        self.nota = QLabel(
            "Nota: 'Compra de hilado' no se usa en los indicadores ni en los gráficos porque una misma "
            "compra puede figurar completa en varias OPs (su monto se ve en la pestaña Resumen). "
            "Pasa el cursor sobre las barras para ver el valor exacto."
        )
        self.nota.setObjectName("notaMuted")
        self.nota.setWordWrap(True)
        lay.addWidget(self.nota)
        lay.addStretch()

    def _nueva_vista(self):
        vista = QChartView()
        vista.setRenderHint(QPainter.RenderHint.Antialiasing)
        vista.setMinimumHeight(320)
        return vista

    # --------------------------------------------------------------- datos
    def limpiar(self):
        self._rows = []
        self.mensaje.setText("Realiza una búsqueda (OP o lote) para ver el dashboard.")
        self.mensaje.show()
        for w in (self.panel_kpis, self.panel_graficos, self.nota):
            w.hide()

    def set_data(self, rows):
        """rows: filas del resumen (op, categoria, kg_netos, valorizado_total, precio_unitario_ponderado)."""
        self._rows = list(rows)
        self.refrescar()

    def refrescar(self):
        if not self._rows:
            return
        self.mensaje.hide()
        for w in (self.panel_kpis, self.panel_graficos, self.nota):
            w.show()

        kg = defaultdict(float)        # categoría -> kg
        usd = defaultdict(float)       # categoría -> US$
        nombre = {}                    # categoría en minúsculas -> texto original
        servicios_op = defaultdict(float)
        for op, cat, kg_n, val, *_ in self._rows:
            clave = str(cat).strip().lower()
            nombre.setdefault(clave, str(cat).strip())
            kg[clave] += to_float(kg_n)
            usd[clave] += to_float(val)
            if clave.startswith("servicio"):
                servicios_op[str(op).strip()] += to_float(val)
        n_ops = len({str(r[0]).strip() for r in self._rows})
        # Dicts normales: leer una categoría ausente no debe crearla (si no, aparece en los
        # gráficos sin nombre original). Por eso se usa .get(..., 0.0) de aquí en adelante.
        kg, usd = dict(kg), dict(usd)

        # Indicadores
        servicios = {nombre[c]: v for c, v in usd.items() if c.startswith("servicio")}
        consumido = kg.get("hilado consumido en tejeduría", 0.0)
        merma = kg.get("hilado merma de tejeduría", 0.0)
        base_merma = consumido + merma
        self.kpi_ops.set_valor(_fmt(n_ops))
        self.kpi_servicios.set_valor(_fmt(sum(servicios.values()), 2))
        self.kpi_tela.set_valor(_fmt(usd.get("compra de tela", 0.0), 2))
        self.kpi_merma.set_valor(f"{merma / base_merma:.2%}" if base_merma else "-")

        # Gráfico 1: flujo valorizado por categoría (divergente: entradas vs. envíos)
        orden = {c: i for i, c in enumerate(ORDEN_CATEGORIAS)}
        cats = sorted((c for c in usd if c != "compra de hilado"), key=lambda c: orden.get(c, 999))
        self.vista_flujo.setMinimumHeight(110 + 28 * len(cats))
        self.vista_flujo.setChart(self._grafico_divergente(
            "Valorizado neto por categoría (US$)", [nombre[c] for c in cats], [usd[c] for c in cats]))

        # Gráfico 2: servicios por tipo (barras ordenadas de mayor a menor)
        serv = sorted(((_nombre_corto_servicio(n), v) for n, v in servicios.items()),
                      key=lambda kv: kv[1], reverse=True)
        self.vista_servicios.setChart(self._grafico_barras(
            "Costo de servicios por tipo (US$)", serv, decimales=0))

        # Gráfico 3: balance de hilado en tejeduría (kg)
        enviado = -kg.get("hilado enviado a tejeduría", 0.0)
        balance = [("Enviado a tejeduría", enviado), ("Consumido", consumido), ("Merma", merma),
                   ("Saldo sin consumir", enviado - consumido - merma)]
        self.vista_hilado.setChart(self._grafico_barras(
            "Balance de hilado en tejeduría (kg)", balance, decimales=1))

        # Gráfico 4: top OPs por costo de servicios (solo tiene sentido en lote)
        self.vista_top.setVisible(n_ops > 1)
        if n_ops > 1:
            top = sorted(servicios_op.items(), key=lambda kv: kv[1], reverse=True)[:TOP_OPS]
            self.vista_top.setChart(self._grafico_barras(
                f"Top {len(top)} OPs por costo de servicios (US$)", [(f"OP {o}", v) for o, v in top]))

    # ------------------------------------------------------------ gráficos
    def _chart_base(self, titulo):
        t = themes.colores()
        chart = QChart()
        chart.setTitle(titulo)
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        chart.setTitleFont(f)
        chart.setTitleBrush(QColor(t["text"]))
        chart.setBackgroundBrush(QColor(t["base"]))
        chart.setBackgroundPen(QPen(QColor(t["border"])))
        chart.setBackgroundRoundness(6)
        chart.setMargins(QMargins(6, 6, 12, 6))
        chart.legend().setLabelColor(QColor(t["text"]))
        chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        return chart

    def _ejes(self, chart, series, categorias, decimales):
        t = themes.colores()
        eje_y = QBarCategoryAxis()
        eje_y.append(categorias)
        eje_y.setLabelsColor(QColor(t["text"]))
        eje_y.setGridLineVisible(False)
        eje_y.setLinePen(QPen(QColor(t["border"])))
        eje_x = QValueAxis()
        eje_x.setLabelFormat(f"%.{decimales}f")
        eje_x.setLabelsColor(QColor(t["muted"]))
        eje_x.setGridLinePen(QPen(QColor(t["grid"]), 1))
        eje_x.setLinePen(QPen(QColor(t["border"])))
        eje_x.setTickCount(5)
        chart.addAxis(eje_y, Qt.AlignmentFlag.AlignLeft)
        chart.addAxis(eje_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(eje_y)
        series.attachAxis(eje_x)
        return eje_x

    @staticmethod
    def _rango_redondo(eje_x, valores):
        """Rango que incluye el 0 y marcas en números redondos."""
        minimo = min([0.0] + list(valores))
        maximo = max([0.0] + list(valores))
        if minimo == maximo:
            maximo = 1.0
        eje_x.setRange(minimo, maximo)
        eje_x.applyNiceNumbers()

    def _conectar_tooltip(self, barset, categorias, valores, unidad):
        def mostrar(estado, indice):
            if estado and 0 <= indice < len(categorias):
                QToolTip.showText(QCursor.pos(), f"{categorias[indice]}\n{unidad} {valores[indice]:,.2f}")
            else:
                QToolTip.hideText()
        barset.hovered.connect(mostrar)

    def _grafico_barras(self, titulo, items, decimales=0):
        """Barras horizontales de un solo color; la primera categoría queda arriba."""
        t = themes.colores()
        chart = self._chart_base(titulo)
        chart.legend().hide()  # Una sola serie: el título la nombra
        items = list(reversed(items))  # QtCharts dibuja la primera categoría abajo
        nombres = [c for c, _ in items]
        valores = [v for _, v in items]
        # Etiqueta directa: el valor formateado (con miles) va junto al nombre en el eje,
        # porque las etiquetas de barra de QtCharts no admiten separador de miles.
        categorias = [f"{c}  ·  {_fmt(v, decimales)}" for c, v in items]

        barset = QBarSet(titulo)
        barset.append(valores)
        barset.setColor(QColor(t["serie_pos"]))
        barset.setBorderColor(QColor(t["base"]))  # separación entre barras
        series = QHorizontalBarSeries()
        series.append(barset)
        series.setBarWidth(0.6)
        chart.addSeries(series)
        eje_x = self._ejes(chart, series, categorias, decimales if decimales <= 1 else 0)
        self._rango_redondo(eje_x, valores)
        self._conectar_tooltip(barset, nombres, valores, "kg" if "(kg)" in titulo else "US$")
        return chart

    def _grafico_divergente(self, titulo, categorias, valores):
        """Entradas/costos (azul, a la derecha) vs. envíos/salidas (rojo, a la izquierda)."""
        t = themes.colores()
        chart = self._chart_base(titulo)
        categorias = list(reversed(categorias))
        valores = list(reversed(valores))

        positivos = QBarSet("Entradas / costos")
        negativos = QBarSet("Envíos / salidas")
        positivos.append([v if v > 0 else 0 for v in valores])
        negativos.append([v if v < 0 else 0 for v in valores])
        for s, color in ((positivos, t["serie_pos"]), (negativos, t["serie_neg"])):
            s.setColor(QColor(color))
            s.setBorderColor(QColor(t["base"]))
            self._conectar_tooltip(s, categorias, valores, "US$")

        series = QHorizontalStackedBarSeries()
        series.append(positivos)
        series.append(negativos)
        series.setBarWidth(0.6)
        chart.addSeries(series)
        eje_x = self._ejes(chart, series, categorias, 0)
        self._rango_redondo(eje_x, valores)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        return chart
