import sqlite3

class Database:
    def __init__(self, file_path):
        self.conn = None
        self.file_path = file_path

    def connect(self):
        self.conn = sqlite3.connect(self.file_path)
        cursor = self.conn.cursor()
        return cursor

    def query(self, sql):
        try:
            cursor = self.connect()
            cursor.execute(sql)
            results = cursor.fetchall()
            cursor.close()
        finally:
            self.conn.close()
        return results


    def update(self, sql):
        result = []
        return result
