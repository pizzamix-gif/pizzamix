import asyncio
import logging
import re
from datetime import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
import database
import keyboards as kb
from states import AdminStates
from utils import PAYMENT_METHOD_LABELS, PAYMENT_STATUS_LABELS, fmt_dt, fmt_price

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

logger = logging.getLogger("mix_bot")

FIELD_LABELS = {"name": "название", "description": "состав", "weight": "вес", "price": "цену"}
SETTINGS_PROMPTS = {
    "work_time": "Введите время работы в формате ЧЧ:ММ-ЧЧ:ММ (например, 10:00-23:00):",
    "delivery_price": "Введите новую цену доставки, ₽:",
    "pizza_address": "Введите адрес пиццерии:",
    "pizza_phone": "Введите телефон пиццерии:",
    "transfer_details": "Введите реквизиты для перевода (банк(и) + номер), например:\nСбербанк: +7 900 123-45-67\nТинькофф: +7 900 123-45-67",
}


def _product_card_text(p) -> str:
    return (
        f"<b>{p['name']}</b>\n"
        f"Категория: {p['category']}\n"
        f"Вес: {p['weight'] or '—'}\n"
        f"Состав: {p['description'] or '—'}\n"
        f"Цена: {fmt_price(p['price'])}₽\n"
        f"Статус: {'✅ активен' if p['is_active'] else '🚫 выключен'}"
    )


def _settings_text(settings) -> str:
    return (
        "⚙️ Настройки\n\n"
        f"⏰ Время работы: {settings['work_start'].strftime('%H:%M')}–{settings['work_end'].strftime('%H:%M')}\n"
        f"🚚 Цена доставки: {fmt_price(settings['delivery_price'])}₽\n"
        f"📍 Адрес: {settings['pizza_address'] or '—'}\n"
        f"☎️ Телефон: {settings['pizza_phone'] or '—'}\n"
        f"💳 Реквизиты для перевода: {settings['transfer_details'] or '⚠️ не заданы'}\n"
        f"🔛 Приём заказов: {'работаем' if settings['is_working'] else 'закрыто'}\n"
        f"📦 Предзаказ: {'включён' if settings['is_preorder'] else 'выключен'}"
    )


# ============================================================================
# Entry points
# ============================================================================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 Админ-панель", reply_markup=kb.admin_main_kb())


@router.callback_query(F.data == "adm:main")
async def adm_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 Админ-панель", reply_markup=kb.admin_main_kb())
    await callback.answer()


@router.callback_query(F.data == "adm_cancel")
async def adm_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.", reply_markup=kb.admin_main_kb())
    await callback.answer()


# ============================================================================
# Menu management
# ============================================================================

@router.callback_query(F.data == "adm:menu")
async def adm_menu(callback: CallbackQuery, pool):
    categories = await database.get_all_categories(pool)
    await callback.message.edit_text("📋 Категории меню:", reply_markup=kb.admin_categories_kb(categories))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cat:"))
async def adm_open_category(callback: CallbackQuery, pool):
    category = callback.data.split(":", 2)[2]
    products = await database.get_products_by_category(pool, category, only_active=False)
    await callback.message.edit_text(category, reply_markup=kb.admin_products_kb(products, category))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:prod:"))
async def adm_open_product(callback: CallbackQuery, pool):
    product_id = int(callback.data.split(":", 2)[2])
    p = await database.get_product(pool, product_id)
    if not p:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await callback.message.edit_text(_product_card_text(p), reply_markup=kb.admin_product_card_kb(p))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:edit:"))
async def adm_edit_field(callback: CallbackQuery, state: FSMContext):
    _, _, product_id, field = callback.data.split(":")
    await state.set_state(AdminStates.waiting_input)
    await state.update_data(action="edit_product_field", product_id=int(product_id), field=field)
    await callback.message.edit_text(
        f"Введите новое значение поля «{FIELD_LABELS.get(field, field)}»:",
        reply_markup=kb.cancel_inline_kb("adm_cancel"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:toggle:"))
async def adm_toggle_product(callback: CallbackQuery, pool):
    product_id = int(callback.data.split(":", 2)[2])
    await database.toggle_product_active(pool, product_id)
    p = await database.get_product(pool, product_id)
    await callback.message.edit_text(_product_card_text(p), reply_markup=kb.admin_product_card_kb(p))
    await callback.answer("Статус обновлён")


@router.callback_query(F.data.startswith("adm:del:"))
async def adm_delete_confirm(callback: CallbackQuery, pool):
    product_id = int(callback.data.split(":", 2)[2])
    p = await database.get_product(pool, product_id)
    if not p:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await callback.message.edit_text(
        f"Удалить «{p['name']}» безвозвратно?", reply_markup=kb.admin_delete_confirm_kb(product_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delyes:"))
async def adm_delete_yes(callback: CallbackQuery, pool):
    product_id = int(callback.data.split(":", 2)[2])
    await database.delete_product(pool, product_id)
    categories = await database.get_all_categories(pool)
    await callback.message.edit_text("🗑 Товар удалён.", reply_markup=kb.admin_categories_kb(categories))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delno:"))
async def adm_delete_no(callback: CallbackQuery, pool):
    product_id = int(callback.data.split(":", 2)[2])
    p = await database.get_product(pool, product_id)
    await callback.message.edit_text(_product_card_text(p), reply_markup=kb.admin_product_card_kb(p))
    await callback.answer()


@router.callback_query(F.data == "adm:add_product")
async def adm_add_product_start(callback: CallbackQuery, pool):
    categories = await database.get_all_categories(pool)
    await callback.message.edit_text(
        "Выберите категорию для нового товара:", reply_markup=kb.admin_add_category_choice_kb(categories)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:addcat:"))
async def adm_add_product_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 2)[2]
    await state.set_state(AdminStates.waiting_input)
    await state.update_data(action="new_product_name", product_data={"category": category})
    await callback.message.edit_text("Введите название товара:", reply_markup=kb.cancel_inline_kb("adm_cancel"))
    await callback.answer()


@router.callback_query(F.data == "adm:newcat")
async def adm_add_product_new_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_input)
    await state.update_data(action="new_category_name", product_data={})
    await callback.message.edit_text(
        "Введите название новой категории (например, 🍰 Десерты):", reply_markup=kb.cancel_inline_kb("adm_cancel")
    )
    await callback.answer()


# ============================================================================
# Settings
# ============================================================================

@router.callback_query(F.data == "adm:settings")
async def adm_settings(callback: CallbackQuery, pool):
    settings = await database.get_settings(pool)
    await callback.message.edit_text(_settings_text(settings), reply_markup=kb.admin_settings_kb(settings))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:set:"))
async def adm_set_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":", 2)[2]
    await state.set_state(AdminStates.waiting_input)
    await state.update_data(action=f"set:{field}")
    await callback.message.edit_text(SETTINGS_PROMPTS[field], reply_markup=kb.cancel_inline_kb("adm_cancel"))
    await callback.answer()


@router.callback_query(F.data == "adm:toggle_working")
async def adm_toggle_working(callback: CallbackQuery, pool):
    await database.toggle_setting_bool(pool, "is_working")
    settings = await database.get_settings(pool)
    await callback.message.edit_text(_settings_text(settings), reply_markup=kb.admin_settings_kb(settings))
    await callback.answer()


@router.callback_query(F.data == "adm:toggle_preorder")
async def adm_toggle_preorder(callback: CallbackQuery, pool):
    await database.toggle_setting_bool(pool, "is_preorder")
    settings = await database.get_settings(pool)
    await callback.message.edit_text(_settings_text(settings), reply_markup=kb.admin_settings_kb(settings))
    await callback.answer()


# ============================================================================
# Orders & stats
# ============================================================================

@router.callback_query(F.data == "adm:orders")
async def adm_orders(callback: CallbackQuery, pool):
    orders = await database.get_recent_orders(pool, limit=10)
    if not orders:
        await callback.message.edit_text("Заказов пока нет.", reply_markup=kb.admin_back_kb())
        await callback.answer()
        return
    lines = ["🧾 Последние заказы:\n"]
    for o in orders:
        who = o["first_name"] or o["username"] or o["telegram_id"]
        pay = PAYMENT_METHOD_LABELS.get(o["payment_method"], o["payment_method"])
        pay_status = PAYMENT_STATUS_LABELS.get(o["payment_status"], o["payment_status"])
        lines.append(
            f"№{o['id']} · {fmt_dt(o['created_at'])} · {who} · "
            f"{fmt_price(o['total_with_delivery'])}₽ · {o['status']} · {pay} ({pay_status})"
        )
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:stats")
async def adm_stats(callback: CallbackQuery, pool):
    stats = await database.get_stats(pool)
    text = (
        "📊 Статистика\n\n"
        f"Всего заказов: {stats['total']['orders_count']}\n"
        f"Общая выручка: {fmt_price(stats['total']['revenue'])}₽\n\n"
        f"Сегодня заказов: {stats['today']['orders_count']}\n"
        f"Выручка сегодня: {fmt_price(stats['today']['revenue'])}₽"
    )
    await callback.message.edit_text(text, reply_markup=kb.admin_back_kb())
    await callback.answer()


# ============================================================================
# Payment confirmation (transfer orders) — the actual anti-spam gate: the
# customer only gets a "we're cooking" message once you tap Confirm here.
# ============================================================================

@router.callback_query(F.data.startswith("payconfirm:"))
async def adm_payment_confirm(callback: CallbackQuery, pool, bot):
    order_id = int(callback.data.split(":", 1)[1])
    order = await database.get_order_with_user(pool, order_id)
    if order["payment_status"] != "pending":
        await callback.answer("Уже обработано", show_alert=True)
        return
    await database.update_order_payment_status(pool, order_id, "confirmed")

    if callback.message.photo:
        await callback.message.edit_caption(caption=f"✅ Оплата подтверждена — заказ №{order_id}")
    else:
        await callback.message.edit_text(f"✅ Оплата подтверждена — заказ №{order_id}")
    await callback.answer()

    try:
        await bot.send_message(
            order["telegram_id"],
            f"💰 Деньги поступили, ваш заказ №{order_id} готовится!",
        )
    except Exception:
        logger.exception("Failed to notify customer about payment confirmation for order %s", order_id)


@router.callback_query(F.data.startswith("paydecline:"))
async def adm_payment_decline(callback: CallbackQuery, pool, bot):
    order_id = int(callback.data.split(":", 1)[1])
    order = await database.get_order_with_user(pool, order_id)
    if order["payment_status"] != "pending":
        await callback.answer("Уже обработано", show_alert=True)
        return
    await database.update_order_payment_status(pool, order_id, "declined")
    await database.update_order_status(pool, order_id, "Отменён (оплата не подтверждена)")

    if callback.message.photo:
        await callback.message.edit_caption(caption=f"❌ Оплата отклонена — заказ №{order_id}")
    else:
        await callback.message.edit_text(f"❌ Оплата отклонена — заказ №{order_id}")
    await callback.answer()

    try:
        await bot.send_message(
            order["telegram_id"],
            f"❌ Оплата по заказу №{order_id} не подтверждена. Попробуйте оформить заказ ещё раз.",
        )
    except Exception:
        logger.exception("Failed to notify customer about payment decline for order %s", order_id)


# ============================================================================
# Promos
# ============================================================================

@router.callback_query(F.data == "adm:promos")
async def adm_promos(callback: CallbackQuery, pool):
    promos = await database.get_promos(pool)
    await callback.message.edit_text("🔥 Акции:", reply_markup=kb.admin_promos_kb(promos))
    await callback.answer()


@router.callback_query(F.data == "adm:add_promo")
async def adm_add_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_input)
    await state.update_data(action="add_promo")
    await callback.message.edit_text("Введите текст акции:", reply_markup=kb.cancel_inline_kb("adm_cancel"))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delpromo:"))
async def adm_delete_promo(callback: CallbackQuery, pool):
    promo_id = int(callback.data.split(":", 2)[2])
    await database.delete_promo(pool, promo_id)
    promos = await database.get_promos(pool)
    await callback.message.edit_text("🔥 Акции:", reply_markup=kb.admin_promos_kb(promos))
    await callback.answer("Акция удалена")


# ============================================================================
# Broadcast
# ============================================================================

@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_input)
    await state.update_data(action="broadcast")
    await callback.message.edit_text(
        "Отправьте текст или фото с подписью для рассылки:",
        reply_markup=kb.cancel_inline_kb("adm_cancel"),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:bc_yes")
async def adm_broadcast_send(callback: CallbackQuery, pool, state: FSMContext, bot):
    data = await state.get_data()
    content = data.get("broadcast_content")
    await state.clear()
    if not content:
        await callback.answer("Нечего отправлять", show_alert=True)
        return

    user_ids = await database.get_all_user_telegram_ids(pool)
    await callback.message.edit_text(f"⏳ Рассылка запущена для {len(user_ids)} пользователей...")
    await callback.answer()

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            if content["type"] == "photo":
                await bot.send_photo(uid, content["file_id"], caption=content["caption"] or None)
            else:
                await bot.send_message(uid, content["text"])
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # stay well under Telegram's flood limits

    await callback.message.answer(f"✅ Рассылка завершена. Отправлено: {sent}, не доставлено: {failed}.")


@router.callback_query(F.data == "adm:bc_no")
async def adm_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.", reply_markup=kb.admin_main_kb())
    await callback.answer()


# ============================================================================
# Generic text-input collector for every admin flow above
# ============================================================================

async def _handle_settings_input(message: Message, pool, state: FSMContext, field: str, text: str):
    if field == "work_time":
        m = re.match(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$", text)
        if not m:
            await message.answer("Формат неверный. Введите как 10:00-23:00:")
            return
        h1, mi1, h2, mi2 = map(int, m.groups())
        if not (0 <= h1 < 24 and 0 <= mi1 < 60 and 0 <= h2 < 24 and 0 <= mi2 < 60):
            await message.answer("Неверное время. Введите как 10:00-23:00:")
            return
        await database.update_setting(pool, "work_start", time(h1, mi1))
        await database.update_setting(pool, "work_end", time(h2, mi2))
    elif field == "delivery_price":
        try:
            value = float(text.replace(",", "."))
            if value < 0:
                raise ValueError
        except ValueError:
            await message.answer("Введите положительное число:")
            return
        await database.update_setting(pool, "delivery_price", value)
    elif field in ("pizza_address", "pizza_phone", "transfer_details"):
        if not text:
            await message.answer("Значение не может быть пустым:")
            return
        await database.update_setting(pool, field, text)

    await state.clear()
    settings = await database.get_settings(pool)
    await message.answer("✅ Настройки обновлены.")
    await message.answer(_settings_text(settings), reply_markup=kb.admin_settings_kb(settings))


@router.message(AdminStates.waiting_input)
async def adm_waiting_input(message: Message, pool, state: FSMContext):
    data = await state.get_data()
    action = data.get("action", "")
    text = (message.text or "").strip()

    if action == "edit_product_field":
        field = data["field"]
        product_id = data["product_id"]
        if field == "price":
            try:
                value = float(text.replace(",", "."))
                if value <= 0:
                    raise ValueError
            except ValueError:
                await message.answer("Цена должна быть положительным числом. Попробуйте ещё раз:")
                return
        else:
            if not text:
                await message.answer("Значение не может быть пустым. Попробуйте ещё раз:")
                return
            value = text
        await database.update_product_field(pool, product_id, field, value)
        await state.clear()
        p = await database.get_product(pool, product_id)
        await message.answer("✅ Обновлено.")
        await message.answer(_product_card_text(p), reply_markup=kb.admin_product_card_kb(p))
        return

    if action == "new_category_name":
        if not text:
            await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
            return
        await state.update_data(action="new_product_name", product_data={"category": text})
        await message.answer("Введите название товара:", reply_markup=kb.cancel_inline_kb("adm_cancel"))
        return

    if action == "new_product_name":
        if not text:
            await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
            return
        product_data = data.get("product_data", {})
        product_data["name"] = text
        await state.update_data(action="new_product_description", product_data=product_data)
        await message.answer("Состав (или «-», если не нужно):", reply_markup=kb.cancel_inline_kb("adm_cancel"))
        return

    if action == "new_product_description":
        product_data = data.get("product_data", {})
        product_data["description"] = "" if text == "-" else text
        await state.update_data(action="new_product_weight", product_data=product_data)
        await message.answer("Вес/объём, например «450 г» (или «-»):", reply_markup=kb.cancel_inline_kb("adm_cancel"))
        return

    if action == "new_product_weight":
        product_data = data.get("product_data", {})
        product_data["weight"] = "" if text == "-" else text
        await state.update_data(action="new_product_price", product_data=product_data)
        await message.answer("Цена, ₽:", reply_markup=kb.cancel_inline_kb("adm_cancel"))
        return

    if action == "new_product_price":
        try:
            price = float(text.replace(",", "."))
            if price <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Цена должна быть положительным числом. Попробуйте ещё раз:")
            return
        product_data = data.get("product_data", {})
        product = await database.add_product(
            pool,
            category=product_data["category"],
            name=product_data["name"],
            description=product_data.get("description", ""),
            weight=product_data.get("weight", ""),
            price=price,
        )
        await state.clear()
        await message.answer(f"✅ Товар «{product['name']}» добавлен.")
        products = await database.get_products_by_category(pool, product["category"], only_active=False)
        await message.answer(product["category"], reply_markup=kb.admin_products_kb(products, product["category"]))
        return

    if action.startswith("set:"):
        await _handle_settings_input(message, pool, state, action.split(":", 1)[1], text)
        return

    if action == "add_promo":
        if not text:
            await message.answer("Текст акции не может быть пустым. Попробуйте ещё раз:")
            return
        await database.add_promo(pool, text)
        await state.clear()
        promos = await database.get_promos(pool)
        await message.answer("✅ Акция добавлена.")
        await message.answer("🔥 Акции:", reply_markup=kb.admin_promos_kb(promos))
        return

    if action == "broadcast":
        if message.photo:
            content = {
                "type": "photo",
                "file_id": message.photo[-1].file_id,
                "caption": message.html_text if (message.text or message.caption) else "",
            }
        elif message.text:
            content = {"type": "text", "text": message.html_text}
        else:
            await message.answer("Поддерживается только текст или фото с подписью. Отправьте ещё раз:")
            return
        await state.update_data(action="broadcast_confirm", broadcast_content=content)
        count = len(await database.get_all_user_telegram_ids(pool))
        await message.answer(
            f"Разослать это сообщение {count} пользователям?", reply_markup=kb.admin_broadcast_confirm_kb()
        )
        return

    # broadcast_confirm and unknown actions: don't leave the admin stuck mid-flow.
    await state.clear()
    await message.answer("Что-то пошло не так, начните заново.", reply_markup=kb.admin_main_kb())
