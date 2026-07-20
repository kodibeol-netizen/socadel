import pymysql, json
config = {
    'host':'127.0.0.1',
    'port':3306,
    'user':'root',
    'password':'',
    'database':'socadel_terrain',
    'charset':'utf8mb4',
    'cursorclass':pymysql.cursors.DictCursor,
}
conn = pymysql.connect(**config)
cur = conn.cursor()
cur.execute("SHOW TABLES LIKE 'synthese_mensuel_odk'")
print('table_exists', bool(cur.fetchone()))
cur.execute("SHOW COLUMNS FROM synthese_mensuel_odk")
cols = cur.fetchall()
print('columns', json.dumps(cols, ensure_ascii=False))
cur.execute("SELECT * FROM synthese_mensuel_odk LIMIT 5")
rows = cur.fetchall()
print('sample_rows', json.dumps(rows, ensure_ascii=False))
conn.close()
