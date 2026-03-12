"""
Simple SQL validation - checks for allowed tables and SELECT-only queries.
"""

import re

ALLOWED_TABLES = {"accrual_transactions"}


class SqlValidationError(Exception):
    """Raised when SQL violates access policy."""


def validate_sql(sql: str) -> None:
    """Basic security check: only SELECT on allowed tables."""
    sql_upper = sql.upper().strip()
    
    # Must be a SELECT (or WITH ... SELECT)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        raise SqlValidationError("Only SELECT queries are allowed")
    
    # Block obvious write operations
    for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]:
        if keyword in sql_upper:
            raise SqlValidationError(f"{keyword} operations are not allowed")
    
    # Check that only allowed tables are referenced
    sql_lower = sql.lower()
    # Simple heuristic: look for FROM/JOIN followed by table name
    table_pattern = r'(?:from|join)\s+([a-z_][a-z0-9_]*)'
    found_tables = set(re.findall(table_pattern, sql_lower))
    
    for table in found_tables:
        if table not in ALLOWED_TABLES and table not in ["(", "select"]:
            raise SqlValidationError(f"Access denied: table '{table}' is not allowed")


def apply_authorization_scope(sql: str, allowed_groups: list[int]) -> str:
    """Add WHERE clause for authorization_group filtering."""
    if not allowed_groups:
        raise SqlValidationError("No authorization groups provided")
    
    groups_csv = ", ".join(str(g) for g in allowed_groups)
    
    # Simple approach: wrap the query in a subquery with filter
    # This works for most simple queries
    if "WHERE" in sql.upper():
        # Add AND clause
        sql = re.sub(
            r'(WHERE\s+)',
            f'\\1authorization_group IN ({groups_csv}) AND ',
            sql,
            count=1,
            flags=re.IGNORECASE
        )
    else:
        # Add WHERE clause before GROUP BY, ORDER BY, LIMIT, or end
        insert_point = re.search(
            r'(GROUP BY|ORDER BY|LIMIT|$)',
            sql,
            re.IGNORECASE
        )
        if insert_point:
            pos = insert_point.start()
            sql = sql[:pos] + f" WHERE authorization_group IN ({groups_csv}) " + sql[pos:]
    
    return sql
