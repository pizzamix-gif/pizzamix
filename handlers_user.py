import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
import database
import keyboards as kb
from states import CheckoutStates
from utils import fmt_dt, fmt_price

router = Router(name="user")
logger = logging.getLogger("mix_bot")

WELCOME = f"🍕 ДОБРО ПОЖАЛОВАТЬ В ПИЦЦЕРИЮ «{config.PIZZERIA_NAME}»!"


# ============================================================================
# Cart helpers — cart lives in FSM data, keyed per chat, independent of
# whatever "state" (if any) the checkout flow is currently in.
# ============================================================================

async def _get_cart(state: FSMContext) -> dict:
    data = await state.get_data()
    return data.get("cart", {})


async def _save_cart(state: FSMContext, cart: dict) -> None:
    await state.update_data(cart=cart)


def _cart_text(cart: dict) -> str:
    if not cart:
        return "🛒 Ваша корзина пуста."
    lines = ["🛒 Ваша корзина:\n"]
    total = 0.0
    for item in cart.values():
        subtotal = item["price"] * item["qty"]
        total += subtotal
        lines.append(f"• {item['name']} × {item['qty']} = {fmt_price(subtotal)}₽")
    lines.append(f"\nИтого: {fmt_price(total)}₽")
    return "\n".join(lines)


# ============================================================================
# /start
# ============================================================================

@router.message(CommandStart())
async def cmd_start(message: Message, pool, state: FSMContext):
    await state.clear()
    await database.get_or_create_user(
        pool, message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    settings = await database.get_settings(pool)
    open_now = settings["is_working"]

    if not open_now and not settings["is_preorder"]:
        await message.answer(
            f"{WELCOME}\n\n⏰ Мы закрыты.\n"
            f"Режим работы: {settings['work_start'].strftime('%H:%M')}–{settings['work_end'].strftime('%H:%M')}.",
            reply_markup=kb.main_reply_kb(order_enabled=False),
        )
        return

    text = WELCOME
    if not open_now and settings["is_preorder"]:
        text += "\n\n⏰ Сейчас мы закрыты, но принимаем предзаказ — соберём его к открытию."
    await message.answer(text, reply_markup=kb.main_reply_kb(order_enabled=True))


# ============================================================================
# Catalog
# ============================================================================

@router.message(F.text == "🍕 Сделать заказ")
async def show_categories(message: Message, pool, state: FSMContext):
    await state.set_state(None)  # abandon any half-finished checkout prompt, keep the cart
    settings = await database.get_settings(pool)
    if not settings["is_working"] and not settings["is_preorder"]:
        await message.answer("⏰ Мы закрыты и сейчас не принимаем даже предзаказы.")
        return
    categories = await database.get_categories(pool)
    if not categories:
        await message.answer("Меню пока пустое, загляните позже 🙏")
        return
    await message.answer("Выберите категорию:", reply_markup=kb.categories_kb(categories))


@router.callback_query(F.data.startswith("cat:"))
async def open_category(callback: CallbackQuery, pool):
    category = callback.data.split(":", 1)[1]
    products = await database.get_products_by_category(pool, category)
    if not products:
        await callback.answer("В этой категории пока нет товаров", show_alert=True)
        return
    await callback.message.edit_text(f"{category}\n\nВыберите товар:", reply_markup=kb.products_kb(products, category))
    await callback.answer()


@router.callback_query(F.data == "back_cats")
async def back_to_categories(callback: CallbackQuery, pool):
    categories = await database.get_categories(pool)
    await callback.message.edit_text("Выберите категорию:", reply_markup=kb.categories_kb(categories))
    await callback.answer()


@router.callback_query(F.data.startswith("back_prods:"))
async def back_to_products(callback: CallbackQuery, pool):
    category = callback.data.split(":", 1)[1]
    products = await database.get_products_by_category(pool, category)
    await callback.message.edit_text(f"{category}\n\nВыберите товар:", reply_markup=kb.products_kb(products, category))
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def open_product(callback: CallbackQuery, pool):
    product_id = int(callback.data.split(":", 1)[1])
    p = await database.get_product(pool, product_id)
    if not p or not p["is_active"]:
        await callback.answer("Этот товар сейчас недоступен", show_alert=True)
        return
    lines = [f"<b>{p['name']}</b>"]
    if p["weight"]:
        lines.append(f"⚖️ Вес: {p['weight']}")
    if p["description"]:
        lines.append(f"🧾 Состав: {p['description']}")
    lines.append(f"💰 Цена: {fmt_price(p['price'])}₽")
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.product_card_kb(product_id, p["category"]))
    await callback.answer()


# ============================================================================
# Cart
# ============================================================================

@router.callback_query(F.data.startswith("addcart:"))
async def add_to_cart(callback: CallbackQuery, pool, state: FSMContext):
    product_id = int(callback.data.split(":", 1)[1])
    p = await database.get_product(pool, product_id)
    if not p or not p["is_active"]:
        await callback.answer("Товар недоступен", show_alert=True)
        return
    cart = await _get_cart(state)
    key = str(product_id)
    if key in cart:
        cart[key]["qty"] += 1
    else:
        cart[key] = {"name": p["name"], "price": float(p["price"]), "qty": 1}
    await _save_cart(state, cart)
    await callback.answer(f"Добавлено: {p['name']} ✅")


@router.message(F.text == "🛒 Корзина")
async def show_cart(message: Message, state: FSMContext):
    await state.set_state(None)
    cart = await _get_cart(state)
    await message.answer(_cart_text(cart), reply_markup=kb.cart_kb(cart))


@router.callback_query(F.data.startswith("cart_inc:"))
async def cart_inc(callback: CallbackQuery, state: FSMContext):
    cart = await _get_cart(state)
    key = callback.data.split(":", 1)[1]
    if key in cart:
        cart[key]["qty"] += 1
        await _save_cart(state, cart)
    await callback.message.edit_text(_cart_text(cart), reply_markup=kb.cart_kb(cart))
    await callback.answer()


@router.callback_query(F.data.startswith("cart_dec:"))
async def cart_dec(callback: CallbackQuery, state: FSMContext):
    cart = await _get_cart(state)
    key = callback.data.split(":", 1)[1]
    if key in cart:
        cart[key]["qty"] -= 1
        if cart[key]["qty"] <= 0:
            del cart[key]
        await _save_cart(state, cart)
    await callback.message.edit_text(_cart_text(cart), reply_markup=kb.cart_kb(cart))
    await callback.answer()


@router.callback_query(F.data.startswith("cart_rm:"))
async def cart_rm(callback: CallbackQuery, state: FSMContext):
    cart = await _get_cart(state)
    cart.pop(callback.data.split(":", 1)[1], None)
    await _save_cart(state, cart)
    await callback.message.edit_text(_cart_text(cart), reply_markup=kb.cart_kb(cart))
    await callback.answer()


@router.callback_query(F.data == "cart_clear")
async def cart_clear(callback: CallbackQuery, state: FSMContext):
    await _save_cart(state, {})
    await callback.message.edit_text(_cart_text({}), reply_markup=kb.cart_kb({}))
    await callback.answer("Корзина очищена")


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


# ============================================================================
# Checkout
# ============================================================================

async def _ask_phone(message: Message, pool, telegram_id: int, state: FSMContext, edit: bool):
    user = await database.get_user_by_telegram_id(pool, telegram_id)
    if user and user["phone"]:
        text = f"☎️ Использовать сохранённый номер?\n\n{user['phone']}"
        markup = kb.use_saved_kb("phone", user["phone"])
    else:
        await state.set_state(CheckoutStates.waiting_phone)
        text = "☎️ Введите номер телефона для связи:"
        markup = kb.cancel_inline_kb("order_cancel")
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _ask_comment(message: Message, state: FSMContext, edit: bool):
    await state.set_state(CheckoutStates.waiting_comment)
    text = "💬 Комментарий к заказу (домофон, этаж и т.п.) — или нажмите «Пропустить»:"
    markup = kb.skip_comment_kb()
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _show_summary(message: Message, pool, state: FSMContext, edit: bool):
    data = await state.get_data()
    cart = data.get("cart", {})
    settings = await database.get_settings(pool)
    delivery_type = data.get("delivery_type")
    delivery_price = float(settings["delivery_price"]) if delivery_type == "delivery" else 0.0
    total = sum(item["price"] * item["qty"] for item in cart.values())

    lines = ["🧾 Проверьте заказ:\n"]
    for item in cart.values():
        lines.append(f"• {item['name']} × {item['qty']} = {fmt_price(item['price'] * item['qty'])}₽")
    lines.append("")
    lines.append("📦 Доставка" if delivery_type == "delivery" else "🏠 Самовывоз")
    if delivery_type == "delivery":
        lines.append(f"Адрес: {data.get('address')}")
        lines.append(f"Стоимость доставки: {fmt_price(delivery_price)}₽")
    lines.append(f"Телефон: {data.get('phone')}")
    if data.get("comment"):
        lines.append(f"Комментарий: {data['comment']}")
    lines.append(f"\n💰 Итого: {fmt_price(total + delivery_price)}₽")

    text = "\n".join(lines)
    if edit:
        await message.edit_text(text, reply_markup=kb.confirm_order_kb())
    else:
        await message.answer(text, reply_markup=kb.confirm_order_kb())


@router.callback_query(F.data == "checkout_start")
async def checkout_start(callback: CallbackQuery, pool, state: FSMContext):
    cart = await _get_cart(state)
    if not cart:
        await callback.answer("Корзина пуста", show_alert=True)
        return
    settings = await database.get_settings(pool)
    if not settings["is_working"] and not settings["is_preorder"]:
        await callback.answer("Сейчас мы не принимаем заказы", show_alert=True)
        return
    await callback.message.edit_text("Как вам удобнее получить заказ?", reply_markup=kb.delivery_type_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("deliv:"))
async def choose_delivery(callback: CallbackQuery, pool, state: FSMContext):
    delivery_type = callback.data.split(":", 1)[1]
    await state.update_data(delivery_type=delivery_type)
    if delivery_type == "delivery":
        user = await database.get_user_by_telegram_id(pool, callback.from_user.id)
        if user and user["address"]:
            await callback.message.edit_text(
                f"📦 Использовать сохранённый адрес доставки?\n\n{user['address']}",
                reply_markup=kb.use_saved_kb("addr", user["address"]),
            )
        else:
            await state.set_state(CheckoutStates.waiting_address)
            await callback.message.edit_text("📍 Введите адрес доставки:", reply_markup=kb.cancel_inline_kb("order_cancel"))
    else:
        await _ask_phone(callback.message, pool, callback.from_user.id, state, edit=True)
    await callback.answer()


@router.message(CheckoutStates.waiting_address)
async def got_address(message: Message, pool, state: FSMContext):
    address = (message.text or "").strip()
    if len(address) < 5:
        await message.answer("Адрес выглядит слишком коротким — уточните, пожалуйста:")
        return
    await state.update_data(address=address)
    await state.set_state(None)
    await _ask_phone(message, pool, message.from_user.id, state, edit=False)


@router.callback_query(F.data.startswith("use:"))
async def use_saved(callback: CallbackQuery, pool, state: FSMContext):
    _, kind, choice = callback.data.split(":")
    user = await database.get_user_by_telegram_id(pool, callback.from_user.id)
    if kind == "addr":
        if choice == "yes":
            await state.update_data(address=user["address"])
            await _ask_phone(callback.message, pool, callback.from_user.id, state, edit=True)
        else:
            await state.set_state(CheckoutStates.waiting_address)
            await callback.message.edit_text("📍 Введите новый адрес доставки:", reply_markup=kb.cancel_inline_kb("order_cancel"))
    else:
        if choice == "yes":
            await state.update_data(phone=user["phone"])
            await _ask_comment(callback.message, state, edit=True)
        else:
            await state.set_state(CheckoutStates.waiting_phone)
            await callback.message.edit_text("☎️ Введите номер телефона:", reply_markup=kb.cancel_inline_kb("order_cancel"))
    await callback.answer()


@router.message(CheckoutStates.waiting_phone)
async def got_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    if len(phone) < 5:
        await message.answer("Похоже, это не номер телефона. Попробуйте ещё раз:")
        return
    await state.update_data(phone=phone)
    await state.set_state(None)
    await _ask_comment(message, state, edit=False)


@router.callback_query(F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, pool, state: FSMContext):
    await state.update_data(comment=None)
    await state.set_state(None)
    await _show_summary(callback.message, pool, state, edit=True)
    await callback.answer()


@router.message(CheckoutStates.waiting_comment)
async def got_comment(message: Message, pool, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await state.set_state(None)
    await _show_summary(message, pool, state, edit=False)


@router.callback_query(F.data == "order_cancel")
async def order_cancel(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(None)
    await state.set_data({"cart": data.get("cart", {})})
    await callback.message.edit_text("Оформление отменено. Корзина сохранена — можно продолжить покупки.")
    await callback.answer()


@router.callback_query(F.data == "order_confirm")
async def order_confirm(callback: CallbackQuery, pool, state: FSMContext, bot):
    data = await state.get_data()
    cart = data.get("cart", {})
    if not cart:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    settings = await database.get_settings(pool)
    delivery_type = data.get("delivery_type", "pickup")
    delivery_price = float(settings["delivery_price"]) if delivery_type == "delivery" else 0.0

    user = await database.get_or_create_user(
        pool, callback.from_user.id, callback.from_user.username, callback.from_user.first_name
    )

    items = [
        {"product_id": int(pid), "name": item["name"], "price": item["price"], "quantity": item["qty"]}
        for pid, item in cart.items()
    ]

    order = await database.create_order(
        pool,
        user_id=user["id"],
        items=items,
        delivery_type=delivery_type,
        address=data.get("address") if delivery_type == "delivery" else None,
        phone=data.get("phone"),
        comment=data.get("comment"),
        delivery_price=delivery_price,
    )

    await database.update_user_contact(
        pool, user["id"],
        phone=data.get("phone"),
        address=data.get("address") if delivery_type == "delivery" else user["address"],
    )

    await state.set_data({})
    await state.set_state(None)

    await callback.message.edit_text(
        f"✅ Заказ №{order['id']} принят!\n"
        f"Статус: {order['status']}\n"
        f"Сумма к оплате: {fmt_price(order['total_with_delivery'])}₽\n\n"
        f"Мы свяжемся с вами в ближайшее время. Спасибо за заказ! 🍕"
    )
    await callback.answer()

    admin_text = (
        f"🆕 Новый заказ №{order['id']}\n"
        f"От: {callback.from_user.full_name} (@{callback.from_user.username or '—'})\n"
        f"Тип: {'📦 Доставка' if delivery_type == 'delivery' else '🏠 Самовывоз'}\n"
    )
    if delivery_type == "delivery":
        admin_text += f"Адрес: {data.get('address')}\n"
    admin_text += f"Телефон: {data.get('phone')}\n"
    if data.get("comment"):
        admin_text += f"Комментарий: {data['comment']}\n"
    admin_text += "\nСостав:\n"
    for item in cart.values():
        admin_text += f"• {item['name']} × {item['qty']}\n"
    admin_text += f"\n💰 Сумма: {fmt_price(order['total_with_delivery'])}₽"

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:
            logger.exception("Failed to notify admin %s about order %s", admin_id, order["id"])


# ============================================================================
# Profile & promos
# ============================================================================

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message, pool, state: FSMContext):
    await state.set_state(None)
    user = await database.get_or_create_user(
        pool, message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    summary = await database.get_user_orders_summary(pool, user["id"])
    orders = await database.get_user_orders(pool, user["id"], limit=5)

    lines = [
        "👤 Ваш профиль",
        f"Имя: {user['first_name'] or '—'}",
        f"Телефон: {user['phone'] or 'не указан'}",
        f"Адрес: {user['address'] or 'не указан'}",
        f"Заказов: {summary['orders_count']}",
        f"Сумма покупок: {fmt_price(summary['total_spent'])}₽",
    ]
    if orders:
        lines.append("\nПоследние заказы:")
        for o in orders:
            lines.append(f"№{o['id']} · {fmt_dt(o['created_at'])} · {fmt_price(o['total_with_delivery'])}₽ · {o['status']}")
    await message.answer("\n".join(lines))


@router.message(F.text == "🔥 Акции")
async def show_promos(message: Message, pool, state: FSMContext):
    await state.set_state(None)
    promos = await database.get_promos(pool)
    if not promos:
        await message.answer("Сейчас активных акций нет — загляните позже 🙂")
        return
    lines = ["🔥 Наши акции:\n"] + [f"• {pr['text']}" for pr in promos[:10]]
    await message.answer("\n".join(lines))


# ============================================================================
# Fallback — keep this LAST so it never shadows the handlers above
# ============================================================================

@router.message(F.text)
async def fallback_text(message: Message):
    await message.answer("Не совсем понимаю 🙂 Используйте кнопки меню ниже.")
