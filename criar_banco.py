"""Cria o banco SQLite em data/clinica.db"""

from database.db import DB_PATH, init_db, get_conn


def main():
    init_db()
    conn = get_conn()
    tabelas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    print(f"Banco criado: {DB_PATH.resolve()}")
    for t in tabelas:
        print(f"  - {t[0]}")


if __name__ == "__main__":
    main()
