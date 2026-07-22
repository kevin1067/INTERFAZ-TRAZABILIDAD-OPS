import os
from config import Config
import sqlite3
class DatabaseManager:
    def __init__(self, db_dir):
        self.db_dir = db_dir

    def get_paths(self):
        return (
            os.path.join(self.db_dir, Config.DB_HILADO),
            os.path.join(self.db_dir, Config.DB_TEJIDOS),
            os.path.join(self.db_dir, Config.DB_RESUMEN)
        )

    def check_health(self):
        path_hilado, path_tejidos, path_resumen = self.get_paths()
        # Modificación: Ahora devuelve el estado de las 3 bases de datos
        return (
            os.path.exists(path_hilado), 
            os.path.exists(path_tejidos), 
            os.path.exists(path_resumen)
        )

    def _conectar_multi(self):
        path_hilado, path_tejidos, path_resumen = self.get_paths()
        
        # Conexión principal (esquema 'main')
        conn = sqlite3.connect(path_hilado)
        
        # Adjuntar las otras bases de datos
        conn.execute(f"ATTACH DATABASE '{path_tejidos}' AS tejidos")
        
        # Modificación: Adjuntamos la base de datos de resumen
        conn.execute(f"ATTACH DATABASE '{path_resumen}' AS resumen")
        
        return conn

    def fetch_data(self, schema, table, headers, lista_ops, order_col=None):
        cols = ", ".join(f'"{c}"' for c, _ in headers if c) # "if c" evita columnas vacías
        all_rows = []
        
        try:
            conn = self._conectar_multi()
            for op_text in lista_ops:
                try:
                    op_num = float(op_text)
                except ValueError:
                    op_num = None

                # Consulta base sin el ORDER BY
                sql = f'SELECT {cols} FROM {schema}."{table}" WHERE TRIM("op") = ? OR "op" = ?'
                
                # Agregamos el ORDER BY solo si order_col tiene un valor válido
                if order_col:
                    sql += f' ORDER BY "{order_col}"'

                cur = conn.execute(sql, (op_text, op_num))
                all_rows.extend(cur.fetchall())
        except sqlite3.Error as e:
            raise Exception(f"Error de base de datos: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
                
        return all_rows
    
    def fetch_data_resumen(self, schema, table, headers, lista_ops):
        cols = ", ".join(f'"{c}"' for c, _ in headers)
        all_rows = []
        
        try:
            conn = self._conectar_multi()
            for op_text in lista_ops:
                try:
                    op_num = float(op_text)
                except ValueError:
                    op_num = None

                sql = f'SELECT {cols} FROM {schema}."{table}" WHERE TRIM("op") = ? OR "op" = ?"'
                cur = conn.execute(sql, (op_text, op_num))
                all_rows.extend(cur.fetchall())
        except sqlite3.Error as e:
            raise Exception(f"Error de base de datos: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
                
        return all_rows
    
    def fetch_data_categoria(self, schema, table, headers, lista_ops, categoria, order_col=None):
        cols = ", ".join(f'"{c}"' for c, _ in headers if c) # Evita columnas vacías
        all_rows = []

        try:
            conn = self._conectar_multi()
            for op_text in lista_ops:
                try:
                    op_num = float(op_text)
                except ValueError:
                    op_num = None

                # CORRECCIÓN 1: Paréntesis alrededor del bloque OR y arreglo de comillas
                sql = f'SELECT {cols} FROM {schema}."{table}" WHERE (TRIM("op") = ? OR "op" = ?) AND TRIM(categoria) = ?'
                
                if order_col:
                    sql += f' ORDER BY "{order_col}"'

                # CORRECCIÓN 2: Se agrega 'categoria' a la tupla de ejecución
                cur = conn.execute(sql, (op_text, op_num, categoria))
                all_rows.extend(cur.fetchall())
        except sqlite3.Error as e:
            raise Exception(f"Error de base de datos: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
                
        return all_rows