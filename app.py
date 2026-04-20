
from __future__ import annotations

import json
import os
import re
import sys
import threading
import webbrowser
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

import requests
from flask import Flask, jsonify, render_template, request

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def base_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def runtime_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = base_path()
RUNTIME_DIR = runtime_path()
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

if load_dotenv:
    env_candidates = [RUNTIME_DIR / ".env", BASE_DIR / ".env"]
    for env_file in env_candidates:
        if env_file.exists():
            load_dotenv(env_file, override=False)
            break

app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))
app.config["JSON_AS_ASCII"] = False

API_BASE_URL = os.getenv("ARTEMOX_BASE_URL", "https://api.artemox.com/v1").rstrip("/")
API_KEY = os.getenv("ARTEMOX_API_KEY", "").strip()
DEFAULT_MODEL = os.getenv("ARTEMOX_MODEL", "gpt-5.4").strip() or "gpt-5.4"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
AUTO_OPEN_BROWSER = os.getenv("AUTO_OPEN_BROWSER", "1").strip() not in {"0", "false", "False"}


def load_json(name: str) -> list[dict[str, Any]]:
    with open(DATA_DIR / f"{name}.json", "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def fmt_float(value: Any) -> float:
    try:
        return round(float(value or 0), 1)
    except Exception:
        return 0.0


def normalize_game(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID") or row.get("id")),
        "title": row.get("Название") or row.get("title") or "Без названия",
        "description": row.get("Описание") or row.get("description") or "Описание пока не добавлено.",
        "category_id": fmt_int(row.get("ID_Категории") or row.get("category_id")),
        "developer_id": fmt_int(row.get("ID_Разработчика") or row.get("developer_id")),
        "price": fmt_int(row.get("Цена_руб") or row.get("price_rub")),
        "rating": fmt_float(row.get("Рейтинг") or row.get("rating")),
        "release_date": row.get("Дата_выхода") or row.get("release_date") or "",
        "platforms": row.get("Платформы") or row.get("platforms") or "",
        "in_stock": (row.get("В_наличии") == "Да") if "В_наличии" in row else bool(row.get("in_stock", False)),
    }


def normalize_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID_Пользователя") or row.get("id")),
        "username": row.get("Имя_пользователя") or row.get("username") or "user",
        "first_name": row.get("Имя") or row.get("first_name") or "",
        "last_name": row.get("Фамилия") or row.get("last_name") or "",
        "email": row.get("Email") or row.get("email") or "",
        "country": row.get("Страна") or row.get("country") or "",
        "phone": row.get("Телефон") or row.get("phone") or "",
        "registered_at": row.get("Дата_регистрации") or row.get("registered_at") or "",
        "last_login": row.get("Последний_вход") or row.get("last_login") or "",
    }


def normalize_category(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID_Категории") or row.get("id")),
        "name": row.get("Название_категории") or row.get("name") or "Категория",
        "description": row.get("Описание_категории") or row.get("description") or "",
        "popularity": row.get("Популярность") or row.get("popularity") or "",
    }


def normalize_developer(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID_Разработчика") or row.get("id")),
        "name": row.get("Название_компании") or row.get("company_name") or "Разработчик",
        "country": row.get("Страна") or row.get("country") or "",
        "website": row.get("Веб_сайт") or row.get("website") or "",
        "founded_year": fmt_int(row.get("Год_основания") or row.get("founded_year")),
    }


def normalize_order(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID_Заказа") or row.get("id")),
        "user_id": fmt_int(row.get("ID_Пользователя") or row.get("user_id")),
        "game_id": fmt_int(row.get("ID_Игры") or row.get("game_id")),
        "status": row.get("Статус_заказа") or row.get("status") or "",
        "amount": fmt_int(row.get("Сумма_заказа_руб") or row.get("amount_rub")),
        "order_date": row.get("Дата_заказа") or row.get("order_date") or "",
        "payment_method": row.get("Способ_оплаты") or row.get("payment_method") or "",
    }


def normalize_review(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID_Отзыва") or row.get("id")),
        "user_id": fmt_int(row.get("ID_Пользователя") or row.get("user_id")),
        "game_id": fmt_int(row.get("ID_Игры") or row.get("game_id")),
        "rating": fmt_int(row.get("Оценка") or row.get("rating")),
        "text": row.get("Текст_отзыва") or row.get("text") or "",
        "created_at": row.get("Дата_отзыва") or row.get("created_at") or "",
        "helpfulness": fmt_int(row.get("Полезность") or row.get("helpfulness")),
    }


def normalize_payment(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID_Платежа") or row.get("id")),
        "order_id": fmt_int(row.get("ID_Заказа") or row.get("order_id")),
        "amount": fmt_int(row.get("Сумма_платежа_руб") or row.get("amount_rub")),
        "status": row.get("Статус_платежа") or row.get("status") or "",
        "method": row.get("Способ_платежа") or row.get("method") or "",
        "paid_at": row.get("Дата_платежа") or row.get("paid_at") or "",
        "fee": fmt_float(row.get("Комиссия_руб") or row.get("fee_rub")),
    }


def normalize_cart(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fmt_int(row.get("ID_Корзины") or row.get("id")),
        "user_id": fmt_int(row.get("ID_Пользователя") or row.get("user_id")),
        "game_id": fmt_int(row.get("ID_Игры") or row.get("game_id")),
        "qty": fmt_int(row.get("Количество") or row.get("qty") or 1),
        "added_at": row.get("Дата_добавления") or row.get("added_at") or "",
        "status": row.get("Статус_корзины") or row.get("status") or "",
    }


GAMES = [normalize_game(x) for x in load_json("games")]
USERS = [normalize_user(x) for x in load_json("users")]
CATEGORIES = [normalize_category(x) for x in load_json("categories")]
DEVELOPERS = [normalize_developer(x) for x in load_json("developers")]
ORDERS = [normalize_order(x) for x in load_json("orders")]
REVIEWS = [normalize_review(x) for x in load_json("reviews")]
PAYMENTS = [normalize_payment(x) for x in load_json("payments")]
CART = [normalize_cart(x) for x in load_json("cart")]

CATEGORY_BY_ID = {x["id"]: x for x in CATEGORIES}
DEVELOPER_BY_ID = {x["id"]: x for x in DEVELOPERS}
GAME_BY_ID = {x["id"]: x for x in GAMES}
USER_BY_ID = {x["id"]: x for x in USERS}


def money(v: int) -> str:
    return f"{v:,}".replace(",", " ") + " ₽"


def cover_gradient(category_name: str) -> str:
    palette = {
        "RPG": "linear-gradient(135deg,#5b21b6,#7c3aed 48%,#c084fc)",
        "Экшен": "linear-gradient(135deg,#b91c1c,#ef4444 52%,#fb7185)",
        "Шутер": "linear-gradient(135deg,#0f766e,#14b8a6 52%,#5eead4)",
        "Спорт": "linear-gradient(135deg,#1d4ed8,#3b82f6 52%,#93c5fd)",
        "Гонки": "linear-gradient(135deg,#9a3412,#f97316 52%,#fdba74)",
        "Стратегия": "linear-gradient(135deg,#365314,#65a30d 52%,#bef264)",
        "Приключения": "linear-gradient(135deg,#a16207,#eab308 52%,#fde68a)",
    }
    return palette.get(category_name, "linear-gradient(135deg,#1f2937,#334155 52%,#64748b)")


def enrich_game(game: dict[str, Any]) -> dict[str, Any]:
    category = CATEGORY_BY_ID.get(game["category_id"], {})
    developer = DEVELOPER_BY_ID.get(game["developer_id"], {})
    reviews = [r for r in REVIEWS if r["game_id"] == game["id"]]
    avg_review = round(mean([r["rating"] for r in reviews]), 1) if reviews else game["rating"]
    return {
        **game,
        "category_name": category.get("name", "Без категории"),
        "developer_name": developer.get("name", "Не указан"),
        "review_count": len(reviews),
        "review_avg": avg_review,
        "short_description": game["description"][:110].rstrip() + ("…" if len(game["description"]) > 110 else ""),
        "cover": cover_gradient(category.get("name", "")),
        "release_year": game["release_date"][:4] if game["release_date"] else "—",
    }


ENRICHED_GAMES = [enrich_game(x) for x in GAMES]


def build_profiles(limit: int = 4) -> list[dict[str, Any]]:
    profiles = []
    for user in USERS[:limit]:
        orders = [o for o in ORDERS if o["user_id"] == user["id"]]
        reviews = [r for r in REVIEWS if r["user_id"] == user["id"]]
        cart = [c for c in CART if c["user_id"] == user["id"]]
        paid_total = sum(o["amount"] for o in orders if o["status"] == "Выполнен")
        fav_counter: Counter[str] = Counter()
        for order in orders:
            game = GAME_BY_ID.get(order["game_id"])
            if game:
                fav_counter[CATEGORY_BY_ID.get(game["category_id"], {}).get("name", "Другое")] += 1
        profiles.append(
            {
                "user": user,
                "orders": [
                    {**o, "game_title": GAME_BY_ID.get(o["game_id"], {}).get("title", "Игра")}
                    for o in sorted(orders, key=lambda x: x["order_date"], reverse=True)[:3]
                ],
                "reviews": [
                    {**r, "game_title": GAME_BY_ID.get(r["game_id"], {}).get("title", "Игра")}
                    for r in sorted(reviews, key=lambda x: x["created_at"], reverse=True)[:2]
                ],
                "cart_count": len(cart),
                "paid_total": paid_total,
                "favorite_categories": [name for name, _ in fav_counter.most_common(3)],
            }
        )
    return profiles


def build_dashboard() -> dict[str, Any]:
    successful_orders = sum(1 for x in ORDERS if x["status"] == "Выполнен")
    paid_volume = sum(x["amount"] for x in ORDERS if x["status"] == "Выполнен")
    latest_reviews = sorted(REVIEWS, key=lambda x: x["created_at"], reverse=True)[:6]
    latest_reviews = [
        {
            **r,
            "username": USER_BY_ID.get(r["user_id"], {}).get("username", "Пользователь"),
            "game_title": GAME_BY_ID.get(r["game_id"], {}).get("title", "Игра"),
        }
        for r in latest_reviews
    ]
    return {
        "stats": {
            "games": len(GAMES),
            "users": len(USERS),
            "successful_orders": successful_orders,
            "paid_volume": money(paid_volume),
        },
        "featured": sorted(ENRICHED_GAMES, key=lambda x: (-x["review_avg"], x["price"]))[:8],
        "new_releases": sorted(ENRICHED_GAMES, key=lambda x: x["release_date"], reverse=True)[:5],
        "latest_reviews": latest_reviews,
        "profiles": build_profiles(),
    }


def ai_context_payload() -> dict[str, Any]:
    return {
        "games": [
            {
                "title": g["title"],
                "category": g["category_name"],
                "price": g["price"],
                "rating": g["review_avg"],
                "platforms": g["platforms"],
                "in_stock": g["in_stock"],
                "description": g["description"],
            }
            for g in ENRICHED_GAMES
        ],
        "profiles": build_profiles(limit=3),
        "latest_reviews": build_dashboard()["latest_reviews"],
    }


def sanitize_ai_answer(text: str) -> str:
    lines = [line.rstrip() for line in str(text or "").splitlines()]
    if not lines:
        return ""

    endings = (
        "если хотите",
        "если нужно",
        "могу также",
        "могу помочь",
        "могу еще",
        "могу ещё",
        "могу сделать",
        "хотите",
        "нужна ли",
        "нужно ли",
    )

    while lines:
        last = lines[-1].strip().lower()
        normalized = re.sub(r"^[^\wа-яё]+", "", last)
        if any(normalized.startswith(x) for x in endings):
            lines.pop()
            continue
        break

    return "\n".join(lines).strip()


@app.get("/")
def index():
    dashboard = build_dashboard()
    return render_template(
        "index.html",
        dashboard=dashboard,
        categories=CATEGORIES,
        default_model=DEFAULT_MODEL,
        api_configured=bool(API_KEY),
        api_base_url=API_BASE_URL,
        initial_data=json.dumps(
            {
                "games": ENRICHED_GAMES,
                "categories": CATEGORIES,
                "profiles": dashboard["profiles"],
                "reviews": dashboard["latest_reviews"],
                "hero": dashboard["stats"],
            },
            ensure_ascii=False,
        ),
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "api_base_url": API_BASE_URL, "api_configured": bool(API_KEY)})


@app.get("/api/catalog")
def api_catalog():
    q = request.args.get("q", "").strip().lower()
    category_id = fmt_int(request.args.get("category_id")) if request.args.get("category_id") else None
    sort = request.args.get("sort", "popular")
    items = ENRICHED_GAMES[:]
    if q:
        items = [
            g
            for g in items
            if q in g["title"].lower()
            or q in g["description"].lower()
            or q in g["category_name"].lower()
            or q in g["developer_name"].lower()
            or q in g["platforms"].lower()
        ]
    if category_id:
        items = [g for g in items if g["category_id"] == category_id]

    if sort == "price_asc":
        items.sort(key=lambda x: x["price"])
    elif sort == "price_desc":
        items.sort(key=lambda x: -x["price"])
    elif sort == "new":
        items.sort(key=lambda x: x["release_date"], reverse=True)
    elif sort == "rating":
        items.sort(key=lambda x: (-x["review_avg"], x["price"]))
    else:
        items.sort(key=lambda x: (-x["review_avg"], x["price"]))

    return jsonify({"items": items, "count": len(items)})


@app.get("/api/game/<int:game_id>")
def api_game(game_id: int):
    game = next((g for g in ENRICHED_GAMES if g["id"] == game_id), None)
    if not game:
        return jsonify({"error": "Игра не найдена"}), 404
    reviews = [r for r in REVIEWS if r["game_id"] == game_id]
    reviews = [
        {
            **r,
            "username": USER_BY_ID.get(r["user_id"], {}).get("username", "Пользователь"),
        }
        for r in sorted(reviews, key=lambda x: (-x["helpfulness"], x["created_at"]), reverse=False)
    ]
    similar = [g for g in ENRICHED_GAMES if g["category_id"] == game["category_id"] and g["id"] != game_id][:4]
    return jsonify({"game": game, "reviews": reviews, "similar": similar})


@app.post("/api/ai")
def api_ai():
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Пустой запрос"}), 400

    model = (data.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    scenario = (data.get("scenario") or "chat").strip()
    api_key = API_KEY or (data.get("api_key") or "").strip()

    if not api_key:
        return jsonify({"error": "API ключ не задан. Укажите ARTEMOX_API_KEY в окружении или передайте api_key."}), 400

    system_prompt = (
        "Ты AI-консультант интернет-магазина видеоигр. Отвечай на русском языке, кратко и структурированно. "
        "Используй только переданный контекст каталога, отзывов и профилей. Не выдумывай игры, заказы и пользователей. "
        "Если данных недостаточно, прямо скажи об этом. "
        "Это одноразовый ответ: не задавай уточняющих вопросов и не предлагай продолжить диалог. "
        "Не добавляй финальные фразы вроде 'если хотите, могу...' или 'обращайтесь'."
    )

    scenario_hints = {
        "search": "Сконцентрируйся на подборе игр по критериям пользователя и объясни выбор списком.",
        "recommend": "Дай персональные рекомендации на основе доступных профилей и истории покупок.",
        "summary": "Сделай краткую сводку по отзывам: что нравится, что критикуют, что стоит учитывать перед покупкой.",
        "chat": "Ответь как дружелюбный консультант магазина.",
    }

    user_content = {
        "scenario": scenario,
        "instruction": scenario_hints.get(scenario, scenario_hints["chat"]),
        "question": prompt,
        "context": ai_context_payload(),
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
                ],
                "temperature": 0.4,
            },
            timeout=120,
        )
        raw = response.text
        if response.status_code != 200:
            return jsonify({"error": f"HTTP {response.status_code}", "raw": raw[:2000]}), 502
        payload = response.json()
        answer = sanitize_ai_answer(payload["choices"][0]["message"]["content"])
        return jsonify({"answer": answer, "model": model, "scenario": scenario})
    except requests.RequestException as e:
        return jsonify({"error": f"Сетевой сбой при обращении к AI API: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Не удалось обработать ответ модели: {e}"}), 500


def open_browser() -> None:
    webbrowser.open_new(f"http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    print(f"Open http://127.0.0.1:{PORT}")
    if AUTO_OPEN_BROWSER:
        threading.Timer(1.0, open_browser).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
