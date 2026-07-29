import database

CAT_PIZZA = "🍕 Пиццы"
CAT_HOT = "🥩 Горячее"
CAT_SNACKS = "🌯 Закуски"

_D = "⌀33 см"  # every pizza is the same diameter

MENU = [
    # --- Пиццы (все 33 см) ---
    dict(category=CAT_PIZZA, name="Маргарита", price=600, weight=f"450 г, {_D}",
         description="Соус, моцарелла, базилик, помидоры"),
    dict(category=CAT_PIZZA, name="Гавайская", price=730, weight=f"590 г, {_D}",
         description="Куриная грудка, моцарелла, ветчина, соус, ананас"),
    dict(category=CAT_PIZZA, name="Ветчина с грибами", price=730, weight=f"600 г, {_D}",
         description="Ветчина, моцарелла, помидоры, соус, шампиньоны, оливки"),
    dict(category=CAT_PIZZA, name="Колбасная", price=730, weight=f"560 г, {_D}",
         description="Ветчина, моцарелла, шампиньоны, огурчик, соус, сервелат, помидоры, масляны"),
    dict(category=CAT_PIZZA, name="Мясная", price=730, weight=f"560 г, {_D}",
         description="Куриная грудка, моцарелла, сервелат, бекон, лук, чесночный соус"),
    dict(category=CAT_PIZZA, name="Сытная", price=730, weight=f"450 г, {_D}",
         description="Куриная грудка, моцарелла, ветчина, помидоры, шампиньоны, соус, лук, чесночный соус"),
    dict(category=CAT_PIZZA, name="Трофейная", price=730, weight=f"500 г, {_D}",
         description="Сервелат, моцарелла, пармезан, мраморный, соус, помидоры, масляны"),
    dict(category=CAT_PIZZA, name="Пепперони", price=730, weight=f"560 г, {_D}",
         description="Пепперони, моцарелла, соус, помидоры"),
    dict(category=CAT_PIZZA, name="С морепродуктами", price=730, weight=f"560 г, {_D}",
         description="Креветки, моцарелла, соус, помидоры"),

    # --- Горячее ---
    dict(category=CAT_HOT, name="Мясо верёвочкой", price=630, weight="500 г",
         description="Свинина, перец болгарский, лук репчатый, морковь, чёрные древесные грибы, томатная паста"),
    dict(category=CAT_HOT, name="Шашлык из курицы", price=389, weight="",
         description="С овощами и лавашем"),
    dict(category=CAT_HOT, name="Картофель фри", price=200, weight="", description=""),

    # --- Закуски ---
    dict(category=CAT_SNACKS, name="Шаурма со свининой и сыром", price=210, weight="",
         description="Новинка! Готовится 30 минут"),
    dict(category=CAT_SNACKS, name="Шаурма с курицей большая", price=300, weight="", description=""),
    dict(category=CAT_SNACKS, name="Шаурма с курицей маленькая", price=180, weight="", description=""),
    dict(category=CAT_SNACKS, name="Бургер с говядиной", price=350, weight="", description=""),
    dict(category=CAT_SNACKS, name="Бургер с курицей", price=300, weight="", description=""),
    dict(category=CAT_SNACKS, name="Блины (фарш, рис)", price=120, weight="1 шт", description=""),
]


async def seed_products(pool) -> None:
    """Keeps the base menu in sync with MENU above on every startup:
    - item already exists (matched by category+name) -> refresh its
      description/weight/price (is_active is never touched, so a product
      you turned off in the admin panel stays off);
    - item is missing -> insert it.
    Products you added by hand through the admin panel (not in this list)
    are left alone."""
    for item in MENU:
        existing = await database.find_product(pool, item["category"], item["name"])
        if existing:
            await database.update_product(
                pool, existing["id"], item["description"], item["weight"], item["price"]
            )
        else:
            await database.add_product(
                pool,
                category=item["category"],
                name=item["name"],
                description=item["description"],
                weight=item["weight"],
                price=item["price"],
            )
