import sqlite3

def get_connection():
    return sqlite3.connect("LinkedIn_Post.db", check_same_thread=False)
