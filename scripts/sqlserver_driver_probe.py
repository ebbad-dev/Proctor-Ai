from __future__ import annotations

import pyodbc


def main() -> None:
    drivers = [
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 18 for SQL Server",
        "SQL Server",
    ]
    servers = ["localhost", ".", "(local)", "localhost\\MSSQLSERVER", "np:\\\\.\\pipe\\sql\\query"]
    suffixes = ["Encrypt=no;TrustServerCertificate=yes;", "TrustServerCertificate=yes;", ""]
    for driver in drivers:
        for server in servers:
            for suffix in suffixes:
                database = "master"
                conn_str = (
                    f"DRIVER={{{driver}}};"
                    f"SERVER={server};"
                    f"DATABASE={database};"
                    "Trusted_Connection=yes;"
                    f"{suffix}"
                )
                try:
                    conn = pyodbc.connect(conn_str, timeout=5, autocommit=True)
                    cur = conn.cursor()
                    cur.execute("SELECT DB_NAME()")
                    print({"ok": True, "driver": driver, "server": server, "suffix": suffix, "database": cur.fetchone()[0]})
                    conn.close()
                    return
                except Exception as exc:
                    print({"ok": False, "driver": driver, "server": server, "suffix": suffix, "error": str(exc).splitlines()[0][:220]})
    raise SystemExit(1)


if __name__ == "__main__":
    main()
