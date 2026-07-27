import asyncpg

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    phone TEXT,
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    weight TEXT NOT NULL DEFAULT '',
    price NUMERIC(10, 2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    total_price NUMERIC(10, 2) NOT NULL,
    delivery_price NUMERIC(10, 2) NOT NULL DEFAULT 0,
    total_with_delivery NUMERIC(10, 2) NOT NULL,
    delivery_type TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'Принят',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    work_start TIME NOT NULL DEFAULT '10:00',
    work_end TIME NOT NULL DEFAULT '23:00',
    delivery_price NUMERIC(10, 2) NOT NULL DEFAULT 200,
    pizza_address TEXT NOT NULL DEFAULT '',
    pizza_phone TEXT NOT NULL DEFAULT '',
    is_working BOOLEAN NOT NULL DEFAULT TRUE,
    is_preorder BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS promos (
    id BIGSERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=config.DATABASE_URL, min_size=1, max_size=10)


async def init_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(SCHEMA)
            await conn.execute(
                "INSERT INTO settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
            )


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

async def get_or_create_user(pool, telegram_id: int, username: str | None, first_name: str | None):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        if row:
            return row
        return await conn.fetchrow(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            telegram_id, username, first_name,
        )


async def get_user_by_telegram_id(pool, telegram_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)


async def update_user_contact(pool, user_id: int, phone: str | None = None, address: str | None = None):
    async with pool.acquire() as conn:
        if phone is not None:
            await conn.execute("UPDATE users SET phone = $1 WHERE id = $2", phone, user_id)
        if address is not None:
            await conn.execute("UPDATE users SET address = $1 WHERE id = $2", address, user_id)


async def get_all_user_telegram_ids(pool) -> list[int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id FROM users")
        return [r["telegram_id"] for r in rows]


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------

async def get_categories(pool, only_active: bool = True) -> list[str]:
    query = "SELECT category FROM products"
    if only_active:
        query += " WHERE is_active = TRUE"
    query += " GROUP BY category ORDER BY MIN(id)"
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
        return [r["category"] for r in rows]


async def get_all_categories(pool) -> list[str]:
    return await get_categories(pool, only_active=False)


async def get_products_by_category(pool, category: str, only_active: bool = True):
    query = "SELECT * FROM products WHERE category = $1"
    if only_active:
        query += " AND is_active = TRUE"
    query += " ORDER BY name"
    async with pool.acquire() as conn:
        return await conn.fetch(query, category)


async def get_product(pool, product_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)


async def add_product(pool, category: str, name: str, description: str, weight: str, price: float):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            INSERT INTO products (category, name, description, weight, price)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            category, name, description, weight, price,
        )


async def update_product_field(pool, product_id: int, field: str, value):
    assert field in {"category", "name", "description", "weight", "price"}
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE products SET {field} = $1 WHERE id = $2", value, product_id)


async def toggle_product_active(pool, product_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE products SET is_active = NOT is_active WHERE id = $1", product_id
        )


async def delete_product(pool, product_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM products WHERE id = $1", product_id)


async def count_products(pool) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM products")


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

async def get_settings(pool):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM settings WHERE id = 1")


async def update_setting(pool, field: str, value):
    assert field in {
        "work_start", "work_end", "delivery_price",
        "pizza_address", "pizza_phone", "is_working", "is_preorder",
    }
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE settings SET {field} = $1 WHERE id = 1", value)


async def toggle_setting_bool(pool, field: str):
    assert field in {"is_working", "is_preorder"}
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE settings SET {field} = NOT {field} WHERE id = 1")


# --------------------------------------------------------------------------
# Orders — created inside a single transaction so concurrent checkouts
# never lose or overwrite each other's items.
# --------------------------------------------------------------------------

async def create_order(
    pool,
    user_id: int,
    items: list[dict],
    delivery_type: str,
    address: str | None,
    phone: str | None,
    comment: str | None,
    delivery_price: float,
):
    total_price = sum(item["price"] * item["quantity"] for item in items)
    total_with_delivery = total_price + (delivery_price if delivery_type == "delivery" else 0)

    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                INSERT INTO orders
                    (user_id, total_price, delivery_price, total_with_delivery,
                     delivery_type, address, phone, comment)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
                """,
                user_id, total_price,
                delivery_price if delivery_type == "delivery" else 0,
                total_with_delivery, delivery_type, address, phone, comment,
            )
            for item in items:
                await conn.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, product_name, quantity, price)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    order["id"], item["product_id"], item["name"], item["quantity"], item["price"],
                )
            return order


async def get_order_items(pool, order_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM order_items WHERE order_id = $1", order_id)


async def get_user_orders(pool, user_id: int, limit: int = 5):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id, limit,
        )


async def get_user_orders_summary(pool, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS orders_count, COALESCE(SUM(total_with_delivery), 0) AS total_spent
            FROM orders WHERE user_id = $1
            """,
            user_id,
        )
        return row


async def get_recent_orders(pool, limit: int = 10):
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT o.*, u.first_name, u.username, u.telegram_id
            FROM orders o
            JOIN users u ON u.id = o.user_id
            ORDER BY o.created_at DESC
            LIMIT $1
            """,
            limit,
        )


async def get_stats(pool):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS orders_count, COALESCE(SUM(total_with_delivery), 0) AS revenue
            FROM orders
            """
        )
        today_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS orders_count, COALESCE(SUM(total_with_delivery), 0) AS revenue
            FROM orders WHERE created_at::date = now()::date
            """
        )
        return {"total": row, "today": today_row}


# --------------------------------------------------------------------------
# Promos
# --------------------------------------------------------------------------

async def get_promos(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM promos ORDER BY created_at DESC")


async def add_promo(pool, text: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "INSERT INTO promos (text) VALUES ($1) RETURNING *", text
        )


async def delete_promo(pool, promo_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM promos WHERE id = $1", promo_id)
