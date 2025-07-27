from sqlglot import parse_one, exp
from src.main_logger import logger

sql_query = "SELECT region, SUM(sales_amount) AS total_sales FROM sales_data GROUP BY region"

def replace_table_names(sql: str, table_mapping: dict) -> str:
    """
    replaces actual tabel names
    """
    try:
        logger.info(f"original sql -> {sql}")
        logger.info(f"tabel mapping : {table_mapping}")
        # Parse SQL into AST
        ast = parse_one(sql)

        # Replace table names
        for table in ast.find_all(exp.Table):
            original_name = table.name
            if original_name.lower() in table_mapping:
                table.set("this", exp.to_identifier(table_mapping[original_name.lower()]))

        return ast.sql()
    except Exception as e:
        logger.exception(f"error in replacing tabel names {e}")
    return sql




