import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

class Db:
    def __init__(self):
        self.cnx = pymysql.connect(
            host="localhost",
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database="gesture_present"
        )
        self.cur = self.cnx.cursor()

    def select(self, q):
        self.cur.execute(q)
        return self.cur.fetchall()

    def selectOne(self, q):
        self.cur.execute(q)
        return self.cur.fetchone()


    def insert(self, q):
        self.cur.execute(q)
        self.cnx.commit()
        return self.cur.lastrowid

    def update(self, q):
        self.cur.execute(q)
        self.cnx.commit()
        return self.cur.rowcount

    def delete(self, q):
        self.cur.execute(q)
        self.cnx.commit()
        return self.cur.rowcount

