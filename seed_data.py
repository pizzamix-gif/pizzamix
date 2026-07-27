import database

CAT_PIZZA = "🍕 Пиццы"
CAT_HOT = "🥩 Горячее"
CAT_SNACKS = "🌯 Закуски"

MENU = [
    # --- Пиццы ---
    dict(category=CAT_PIZZA, name="Маргарита", price=600, weight="450 г",
         description="Соус, моцарелла, базилик, помидоры"),
    dict(category=CAT_PIZZA, name="Гавайская", price=730, weight="590 г",
         description="Куриная грудка, моцарелла, ветчина, соус, ананас"),
    dict(category=CAT_PIZZA, name="Ветчина с грибами", price=730, weight="600 г",
         description="Ветчина, моцарелла, помидоры, соус, шампиньоны, оливки"),
    dict(category=CAT_PIZZA, name="Колбасная", price=730, weight="560 г", description=""),
    dict(category=CAT_PIZZA, name="Мясная", price=730, weight="560 г", description=""),
    dict(category=CAT_PIZZA, name="Сытная", price=730, weight="450 г", description=""),
    dict(category=CAT_PIZZA, name="Трофейная", price=730, weight="500 г", description=""),
    dict(category=CAT_PIZZA, name="Пепперони", price=730, weight="560 г", description=""),
    dict(category=CAT_PIZZA, name="С морепродуктами", price=730, weight="560 г", description=""),

    # --- Горячее ---
    dict(category=CAT_HOT, name="Мясо верёвочкой", price=630, weight="", description=""),
    dict(category=CAT_HOT, name="Шашлык из курицы", price=389, weight="", description=""),
    dict(category=CAT_HOT, name="Картофель фри", price=200, weight="", description=""),

    # --- Закуски ---
    dict(category=CAT_SNACKS, name="Шаурма со свининой и сыром", price=210, weight="", description=""),
    dict(category=CAT_SNACKS, name="Шаурма с курицей большая", price=300, weight="", description=""),
    dict(category=CAT_SNACKS, name="Шаурма с курицей маленькая", price=180, weight="", description=""),
    dict(category=CAT_SNACKS, name="Бургер с говядиной", price=350, weight="", description=""),
    dict(category=CAT_SNACKS, name="Бургер с курицей", price=300, weight="", description=""),
    dict(category=CAT_SNACKS, name="Блины", price=120, weight="", description=""),
]


async def seed_products(pool) -> None:
    """Seed the menu only on a fresh database — never overwrites existing rows,
    so re-deploys and restarts don't touch anything the admin has since edited."""
    existing = await database.count_products(pool)
    if existing > 0:
        return
    for item in MENU:
        await database.add_product(
            pool,
            category=item["category"],
            name=item["name"],
            description=item["description"],
            weight=item["weight"],
            price=item["price"],
        )
