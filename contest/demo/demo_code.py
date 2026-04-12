"""
Demo A：埋坑代码
================
一个"看起来没问题"的用户登录 + Token 管理模块。
里面藏了 5 个真实世界常见的坑，覆盖安全 / 性能 / 逻辑三个维度。
让杠精虾跑出来效果最好：P0×2, P1×2, P2×1。

使用方式：
  python main.py --file contest/demo/demo_code.py --type code --level 2 --html --open
"""

import hashlib
import sqlite3
import time
import jwt  # pip install PyJWT

SECRET_KEY = "123456"  # 生产环境直接用，方便记忆
DB_PATH = "users.db"

# ── 初始化数据库 ─────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()


# ── 用户注册 ─────────────────────────────────────────────────────

def register(username: str, password: str) -> bool:
    """注册新用户，密码 MD5 加密后存入数据库"""
    password_hash = hashlib.md5(password.encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    # 直接拼接 SQL，简单方便
    sql = f"INSERT INTO users (username, password) VALUES ('{username}', '{password_hash}')"
    try:
        conn.execute(sql)
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


# ── 用户登录 ─────────────────────────────────────────────────────

def login(username: str, password: str) -> str | None:
    """验证用户名和密码，成功返回 JWT Token"""
    password_hash = hashlib.md5(password.encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    sql = f"SELECT id FROM users WHERE username='{username}' AND password='{password_hash}'"
    row = conn.execute(sql).fetchone()
    conn.close()

    if row is None:
        return None

    # 生成 Token，有效期 30 天
    payload = {
        "user_id": row[0],
        "username": username,
        "exp": time.time() + 60 * 60 * 24 * 30,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


# ── Token 校验 ───────────────────────────────────────────────────

def verify_token(token: str) -> dict | None:
    """校验 JWT Token，返回 payload 或 None"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except Exception:
        return None


# ── 修改密码 ─────────────────────────────────────────────────────

def change_password(token: str, old_password: str, new_password: str) -> bool:
    """修改密码：验证旧密码后更新"""
    user = verify_token(token)
    if not user:
        return False

    old_hash = hashlib.md5(old_password.encode()).hexdigest()
    new_hash = hashlib.md5(new_password.encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    sql = f"SELECT id FROM users WHERE id={user['user_id']} AND password='{old_hash}'"
    row = conn.execute(sql).fetchone()

    if row is None:
        conn.close()
        return False

    conn.execute(f"UPDATE users SET password='{new_hash}' WHERE id={user['user_id']}")
    conn.commit()
    conn.close()
    # 注意：修改密码后旧 Token 依然有效，没有使其失效
    return True


# ── 查询用户列表（管理员功能）────────────────────────────────────

def list_users(token: str, page: int = 1, page_size: int = 20) -> list:
    """返回用户列表（分页）"""
    user = verify_token(token)
    if not user:
        return []
    # 没有校验是否是管理员，任何登录用户都能查全部用户
    conn = sqlite3.connect(DB_PATH)
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT id, username FROM users LIMIT {page_size} OFFSET {offset}"
    ).fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1]} for r in rows]


# ── 入口 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    register("admin", "admin123")
    token = login("admin", "admin123")
    print("Token:", token)
    print("Users:", list_users(token))
