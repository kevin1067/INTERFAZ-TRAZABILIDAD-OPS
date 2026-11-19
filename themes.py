"""
Temas claro / oscuro de la interfaz.

Todos los colores salen de TEMAS; ningún widget debe tener colores fijos.
Combinaciones texto/fondo verificadas con contraste WCAG >= 4.5:1.
"""
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QTableWidget

# Marca de estilo en una celda: "subtotal" | "total" | "positivo" | "negativo"
ROLE_ESTILO = Qt.ItemDataRole.UserRole + 1

OPCIONES = {"Sistema": "sistema", "Claro": "claro", "Oscuro": "oscuro"}

TEMAS = {
    "claro": {
        "window": "#F5F6F8", "base": "#FFFFFF", "alt": "#F2F4F7", "text": "#1F2328",
        "muted": "#5A6270", "border": "#C9D0DA",
        "subtotal": "#E6EBF2", "total": "#D3DCE8", "total_text": "#111418",
        "positivo": "#1B7A3A", "negativo": "#C0262D",
        "sel": "#CFE0F5", "sel_text": "#0B1A2E",
        "btn": "#FFFFFF", "btn_text": "#1F2328", "btn_hover": "#EAF0F8", "btn_pressed": "#D6E1EF",
        # Gráficos (validados con el validador de paletas: CVD y contraste >= 3:1 sobre "base")
        "serie_pos": "#2A78D6", "serie_neg": "#E34948", "grid": "#E1E0D9",
    },
    "oscuro": {
        "window": "#1E1F22", "base": "#2B2D30", "alt": "#313338", "text": "#E6E7EA",
        "muted": "#A9AFB8", "border": "#4A4E55",
        "subtotal": "#3A3F47", "total": "#45505E", "total_text": "#FFFFFF",
        "positivo": "#6FD08C", "negativo": "#FF8A80",
        "sel": "#2F4F7A", "sel_text": "#FFFFFF",
        "btn": "#3A3D42", "btn_text": "#E6E7EA", "btn_hover": "#464A50", "btn_pressed": "#2A2C30",
        "serie_pos": "#3987E5", "serie_neg": "#E66767", "grid": "#3A3D42",
    },
}

_settings = QSettings("TrazabilidadOPS", "Interfaz")
_preferencia = "sistema"   # lo que eligió el usuario
_actual = "claro"          # tema efectivo aplicado
_observadores = []         # funciones a llamar cuando cambia el tema (ej. redibujar gráficos)


def al_cambiar_tema(funcion):
    """Registra una función sin argumentos que se ejecuta tras aplicar un tema."""
    _observadores.append(funcion)


def preferencia_guardada():
    valor = _settings.value("tema", "sistema")
    return valor if valor in OPCIONES.values() else "sistema"


def preferencia():
    return _preferencia


def colores():
    return TEMAS[_actual]


def _tema_del_sistema():
    try:
        oscuro = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # Qt < 6.5
        oscuro = False
    return "oscuro" if oscuro else "claro"


def _paleta(t):
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["window"], QPalette.ColorRole.WindowText: t["text"],
        QPalette.ColorRole.Base: t["base"], QPalette.ColorRole.AlternateBase: t["alt"],
        QPalette.ColorRole.Text: t["text"], QPalette.ColorRole.Button: t["btn"],
        QPalette.ColorRole.ButtonText: t["btn_text"], QPalette.ColorRole.ToolTipBase: t["base"],
        QPalette.ColorRole.ToolTipText: t["text"], QPalette.ColorRole.Highlight: t["sel"],
        QPalette.ColorRole.HighlightedText: t["sel_text"], QPalette.ColorRole.PlaceholderText: t["muted"],
        QPalette.ColorRole.BrightText: t["negativo"],
    }
    for rol, color in roles.items():
        p.setColor(rol, QColor(color))
    # Widgets deshabilitados (ej. campo OP en modo lote)
    for rol in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, rol, QColor(t["muted"]))
    return p


def _hoja_estilos(t):
    return f"""
        QToolTip {{ color: {t['text']}; background-color: {t['base']}; border: 1px solid {t['border']}; }}
        QTableWidget {{ gridline-color: {t['border']}; }}
        QTableWidget::item:selected {{ background-color: {t['sel']}; color: {t['sel_text']}; }}
        QHeaderView::section {{
            background-color: {t['window']}; color: {t['text']}; font-weight: bold;
            border: none; border-right: 1px solid {t['border']}; border-bottom: 1px solid {t['border']};
            padding: 4px 6px;
        }}
        QPushButton#btnDetalle {{
            background-color: {t['btn']}; color: {t['btn_text']}; border: 1px solid {t['border']};
            border-radius: 4px; padding: 4px 8px; font-size: 11px;
        }}
        QPushButton#btnDetalle:hover {{ background-color: {t['btn_hover']}; }}
        QPushButton#btnDetalle:pressed {{ background-color: {t['btn_pressed']}; }}
        QPushButton#btnExportar {{
            background-color: #2E7D32; color: #FFFFFF; font-weight: bold;
            padding: 6px 16px; border-radius: 4px; border: none;
        }}
        QPushButton#btnExportar:hover {{ background-color: #388E3C; }}
        QPushButton#btnExportar:pressed {{ background-color: #1B5E20; }}
        QFrame#kpiTile {{
            background-color: {t['base']}; border: 1px solid {t['border']}; border-radius: 6px;
        }}
        QLabel#kpiTitulo {{ color: {t['muted']}; font-size: 11px; }}
        QLabel#kpiValor {{ color: {t['text']}; font-size: 22px; font-weight: bold; }}
        QLabel#notaMuted {{ color: {t['muted']}; }}
        QLabel#totalLabel {{
            background-color: {t['total']}; color: {t['total_text']};
            padding: 6px; border-radius: 4px;
        }}
    """


def recolorear_tabla(tabla):
    """Aplica los colores del tema actual a las celdas marcadas con ROLE_ESTILO."""
    t = colores()
    for r in range(tabla.rowCount()):
        for c in range(tabla.columnCount()):
            item = tabla.item(r, c)
            estilo = item.data(ROLE_ESTILO) if item else None
            if estilo in ("subtotal", "total"):
                item.setBackground(QColor(t[estilo]))
                item.setForeground(QColor(t["total_text"]))
            elif estilo in ("positivo", "negativo"):
                item.setForeground(QColor(t[estilo]))


def aplicar_tema(app, eleccion=None, guardar=False):
    """eleccion: 'sistema' | 'claro' | 'oscuro'. Sin valor, usa la preferencia guardada."""
    global _preferencia, _actual
    _preferencia = eleccion or preferencia_guardada()
    _actual = _tema_del_sistema() if _preferencia == "sistema" else _preferencia
    if guardar:
        _settings.setValue("tema", _preferencia)

    t = TEMAS[_actual]
    app.setStyle("Fusion")  # El estilo nativo de Windows ignora parte de la paleta
    app.setPalette(_paleta(t))
    app.setStyleSheet(_hoja_estilos(t))

    for widget in app.allWidgets():
        if isinstance(widget, QTableWidget):
            recolorear_tabla(widget)
    for funcion in _observadores:
        funcion()


def seguir_cambios_del_sistema(app):
    """Si la preferencia es 'Sistema', reaplica el tema cuando Windows cambia entre claro/oscuro."""
    try:
        app.styleHints().colorSchemeChanged.connect(
            lambda *_: aplicar_tema(app, "sistema") if _preferencia == "sistema" else None
        )
    except AttributeError:  # Qt < 6.5
        pass
