import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from mysql.connector import errorcode
from config import DB_CONFIG

def init_database():
    cnx = mysql.connector.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        port=DB_CONFIG['port']
    )
    cursor = cnx.cursor()


    try:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET 'utf8mb4'"
        )
    except mysql.connector.Error as err:
        print(f"Failed creating database: {err}")
        exit(1)


    cnx.database = DB_CONFIG['database']


    TABLES = {}
    TABLES['materials'] = (
        "CREATE TABLE IF NOT EXISTS materials ("
        "id VARCHAR(36) PRIMARY KEY,"  
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "product_name VARCHAR(255),"
        "tags TEXT,"
        "platform VARCHAR(50) NOT NULL,"
        "target VARCHAR(255) NOT NULL,"
        "fetch_params JSON,"
        "ai_summary TEXT,"
        "raw_data JSON NOT NULL"
        ")"
    )


    for table_name in TABLES:
        table_description = TABLES[table_name]
        try:
            print(f"Creating table {table_name}: ", end='')
            cursor.execute(table_description)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                print("already exists.")
            else:
                print(err.msg)
        else:
            print("OK")

    cursor.close()
    cnx.close()

if __name__ == "__main__":
    init_database()