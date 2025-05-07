"""
数据库初始化脚本
此模块用于创建SQLite数据库并初始化示例数据

主要功能:
1. 创建users表和orders表
2. 设置表之间的外键关联
3. 插入示例用户数据
4. 插入示例订单数据

数据库结构:
- users表: 用户信息(id, name, age, email)
- orders表: 订单信息(id, user_id, product_name, price, order_date)

作者: 程序员寒山
创建日期: 2025-05-07
"""

import sqlite3

def create_database():
    # 连接到数据库（如果不存在则创建）
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER,
        email TEXT
    )
    ''')

    # 创建订单表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        product_name TEXT NOT NULL,
        price REAL,
        order_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 插入示例用户数据
    users = [
        (1, '张三', 25, 'zhangsan@example.com'),
        (2, '李四', 30, 'lisi@example.com'),
        (3, '王五', 35, 'wangwu@example.com')
    ]
    cursor.executemany('INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)', users)

    # 插入示例订单数据
    orders = [
        (1, 1, '笔记本电脑', 6999.99, '2025-04-01'),
        (2, 1, '手机', 4999.99, '2025-04-15'),
        (3, 2, '平板电脑', 3999.99, '2025-04-20'),
        (4, 3, '耳机', 999.99, '2025-05-01')
    ]
    cursor.executemany('INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?)', orders)

    # 提交更改并关闭连接
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_database()
    print("数据库和示例数据创建完成！")
