"""
Trazabilidad de OP - Hilado y Tela (Multi-DB)
Arquitectura Refactorizada
"""
from pathlib import Path


# =====================================================================
# MÓDULO 1: config.py (Configuraciones y Constantes)
# =====================================================================
class Config:
    #DEFAULT_DIR = Path(r"C:\Users\kzevallos\Desktop\Implementaciones\TRAZABILIDAD-OPS\migracion")
    DEFAULT_DIR = Path(r"\\STNFSAPPRD01\Costos\Sunat 2025\Costo x Cliente 2025\BD Analiticos\Textil_Trazabilidad-no-borrar\migracion")
    DB_HILADO = "control_hilados.db"
    DB_TEJIDOS = "control_tejidos.db"
    DB_RESUMEN = "resumen_op.db"

    HILADO_HEADERS = [
        ("op", "OP Referencial"), ("cod_hilado", "Cod. Hilado"), ("fecha", "Fecha"),
        ("tipo_mov", "Tipo"), ("categoria", "Categoria"), ("proveedor", "Proveedor"),
        ("transaccion", "Transacción"), ("num_mov", "Núm. Mov."), ("guia", "Guía"),
        ("oc", "OC"), ("factura", "Factura"), ("kgs", "Kgs"), ("dolares", "US$"),
        ("cu_usd", "C.U. US$"), ("cu_usd_calc", "C.U.Real$") 
    ]

    TEJIDO_HEADERS = [
        ("op", "OP Referencial"), ("partida", "Partida"), ("cod_tela", "Cod. Tela"),
        ("des_tela", "Descripción Tela"), ("des_comb", "Comb."), ("cod_color", "Cod. Color"),
        ("des_color", "Descripción Color"), ("categoria", "Categoria"),
        ("transaccion", "Transacción"), ("cliente", "Cliente"), ("proveedor", "Proveedor"),
        ("fecha", "Fecha"), ("guia", "Guía"), ("oc", "OC"), ("factura", "Factura"),
        ("kgs", "Kgs"), ("dolares", "US$"), ("cu_usd", "C.U. US$"),("cu_usd_calc", "C.U.Real$")
    ]
    RESUMEN_HEADERS = [
        ("op", "op"), ("categoria","categoria"), ("kg_netos","kg_netos"), ("valorizado_total","valorizado_total"), ("precio_unitario_ponderado","precio_unitario_ponderado")
    ]