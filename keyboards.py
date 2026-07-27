from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import fmt_price

# ============================================================================
# Client — reply keyboard (persistent bottom menu)
# ============================================================================

def main_reply_kb(order_enabled: bool = True) -> ReplyKeyboardMarkup:
    rows = []
    if order_enabled:
        rows.append([KeyboardButton(text="🍕 Сделать заказ")])
    rows.append([KeyboardButton(text="🔥 Акции"), KeyboardButton(text="👤 Мой профиль")])
    rows.append([KeyboardButton(text="🛒 Корзина")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# ============================================================================
# Client — inline keyboards
# ============================================================================

def categories_kb(categories: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cat in categories:
        b.button(text=cat, callback_data=f"cat:{cat}")
    b.adjust(1)
    return b.as_markup()


def products_kb(products, category: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"{p['name']} — {fmt_price(p['price'])}₽", callback_data=f"prod:{p['id']}")
    b.button(text="⬅️ Назад к категориям", callback_data="back_cats")
    b.adjust(1)
    return b.as_markup()


def product_card_kb(product_id: int, category: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Добавить в корзину", callback_data=f"addcart:{product_id}")
    b.button(text="⬅️ Назад", callback_data=f"back_prods:{category}")
    b.adjust(1)
    return b.as_markup()


def cart_kb(items: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for pid, item in items.items():
        b.row(
            InlineKeyboardButton(text="➖", callback_data=f"cart_dec:{pid}"),
            InlineKeyboardButton(text=f"{item['name']} × {item['qty']}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_inc:{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"cart_rm:{pid}"),
        )
    if items:
        b.row(InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout_start"))
        b.row(InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="cart_clear"))
    b.row(InlineKeyboardButton(text="🍕 Продолжить покупки", callback_data="back_cats"))
    return b.as_markup()


def delivery_type_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📦 Доставка", callback_data="deliv:delivery")
    b.button(text="🏠 Самовывоз", callback_data="deliv:pickup")
    b.adjust(1)
    return b.as_markup()


def use_saved_kb(kind: str, value: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    short = value if len(value) <= 30 else value[:27] + "..."
    b.button(text=f"✅ {short}", callback_data=f"use:{kind}:yes")
    b.button(text="✏️ Ввести новый", callback_data=f"use:{kind}:new")
    b.adjust(1)
    return b.as_markup()


def skip_comment_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Пропустить", callback_data="skip_comment")
    return b.as_markup()


def confirm_order_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить заказ", callback_data="order_confirm")
    b.button(text="❌ Отмена", callback_data="order_cancel")
    b.adjust(1)
    return b.as_markup()


def cancel_inline_kb(callback_data: str = "adm_cancel") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data=callback_data)
    return b.as_markup()


# ============================================================================
# Admin
# ============================================================================

def admin_main_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📋 Меню", callback_data="adm:menu")
    b.button(text="⚙️ Настройки", callback_data="adm:settings")
    b.button(text="🧾 Заказы", callback_data="adm:orders")
    b.button(text="📊 Статистика", callback_data="adm:stats")
    b.button(text="🔥 Акции", callback_data="adm:promos")
    b.button(text="📢 Рассылка", callback_data="adm:broadcast")
    b.adjust(2)
    return b.as_markup()


def admin_categories_kb(categories: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cat in categories:
        b.button(text=cat, callback_data=f"adm:cat:{cat}")
    b.button(text="➕ Добавить товар", callback_data="adm:add_product")
    b.button(text="⬅️ В админ-меню", callback_data="adm:main")
    b.adjust(1)
    return b.as_markup()


def admin_products_kb(products, category: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        mark = "✅" if p["is_active"] else "🚫"
        b.button(text=f"{mark} {p['name']} — {fmt_price(p['price'])}₽", callback_data=f"adm:prod:{p['id']}")
    b.button(text="➕ Добавить товар", callback_data="adm:add_product")
    b.button(text="⬅️ К категориям", callback_data="adm:menu")
    b.adjust(1)
    return b.as_markup()


def admin_product_card_kb(product) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Название", callback_data=f"adm:edit:{product['id']}:name")
    b.button(text="📝 Состав", callback_data=f"adm:edit:{product['id']}:description")
    b.button(text="⚖️ Вес", callback_data=f"adm:edit:{product['id']}:weight")
    b.button(text="💰 Цена", callback_data=f"adm:edit:{product['id']}:price")
    toggle_text = "🚫 Выключить" if product["is_active"] else "✅ Включить"
    b.button(text=toggle_text, callback_data=f"adm:toggle:{product['id']}")
    b.button(text="🗑 Удалить", callback_data=f"adm:del:{product['id']}")
    b.button(text="⬅️ Назад", callback_data=f"adm:cat:{product['category']}")
    b.adjust(2, 2, 1, 1, 1)
    return b.as_markup()


def admin_delete_confirm_kb(product_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"adm:delyes:{product_id}")
    b.button(text="❌ Нет", callback_data=f"adm:delno:{product_id}")
    b.adjust(1)
    return b.as_markup()


def admin_add_category_choice_kb(categories: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cat in categories:
        b.button(text=cat, callback_data=f"adm:addcat:{cat}")
    b.button(text="➕ Новая категория", callback_data="adm:newcat")
    b.button(text="❌ Отмена", callback_data="adm:menu")
    b.adjust(1)
    return b.as_markup()


def admin_settings_kb(settings) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⏰ Время работы", callback_data="adm:set:work_time")
    b.button(text="🚚 Цена доставки", callback_data="adm:set:delivery_price")
    b.button(text="📍 Адрес", callback_data="adm:set:pizza_address")
    b.button(text="☎️ Телефон", callback_data="adm:set:pizza_phone")
    work_text = "⛔ Закрыть приём заказов" if settings["is_working"] else "🔛 Открыть приём заказов"
    b.button(text=work_text, callback_data="adm:toggle_working")
    preorder_text = "📦 Выключить предзаказ" if settings["is_preorder"] else "📦 Включить предзаказ"
    b.button(text=preorder_text, callback_data="adm:toggle_preorder")
    b.button(text="⬅️ В админ-меню", callback_data="adm:main")
    b.adjust(2, 2, 1, 1, 1)
    return b.as_markup()


def admin_promos_kb(promos) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for pr in promos:
        preview = pr["text"] if len(pr["text"]) <= 25 else pr["text"][:22] + "..."
        b.button(text=f"🗑 {preview}", callback_data=f"adm:delpromo:{pr['id']}")
    b.button(text="➕ Добавить акцию", callback_data="adm:add_promo")
    b.button(text="⬅️ В админ-меню", callback_data="adm:main")
    b.adjust(1)
    return b.as_markup()


def admin_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить всем", callback_data="adm:bc_yes")
    b.button(text="❌ Отмена", callback_data="adm:bc_no")
    b.adjust(1)
    return b.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ В админ-меню", callback_data="adm:main")
    return b.as_markup()
