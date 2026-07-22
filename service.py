import pandas as pd
class ExcelService:
    @staticmethod
    def load_ops_from_excel(filepath):
        df = pd.read_excel(filepath)
        df.columns = df.columns.str.strip().str.upper()
        
        if "OP" not in df.columns:
            raise ValueError("El archivo Excel no tiene la columna 'OP'.")
            
        serie_limpia = df['OP'].dropna().astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        ops_lote = serie_limpia[serie_limpia != ''].unique().tolist()
        return ops_lote

    @staticmethod
    def export_tables_to_excel(filepath, df_hilado, df_tejido):
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            if not df_hilado.empty:
                df_hilado.to_excel(writer, sheet_name='Trazabilidad Hilado', index=False)
            if not df_tejido.empty:
                df_tejido.to_excel(writer, sheet_name='Trazabilidad Tela', index=False)

def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0