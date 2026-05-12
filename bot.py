import asyncio
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes


TOKEN_ENV_NAME = "TELEGRAM_BOT_TOKEN"
WEBAPP_URL_ENV_NAME = "TELEGRAM_WEBAPP_URL"
WEBHOOK_URL_ENV_NAME = "TELEGRAM_WEBHOOK_URL"
SUPABASE_URL_ENV_NAME = "SUPABASE_URL"
SUPABASE_SERVICE_ROLE_KEY_ENV_NAME = "SUPABASE_SERVICE_ROLE_KEY"
SUPABASE_ANON_KEY_ENV_NAME = "SUPABASE_ANON_KEY"
PUBLIC_API_BASE_URL_ENV_NAME = "PUBLIC_API_BASE_URL"
EMPTY = "·"
SYMBOL_EMOJI = {"X": "❎", "O": "⭕"}
BOT_MISTAKE_CHANCE = 0.30
BOT_MOVE_DELAY_SECONDS = 0.8
STATS_FILE = Path(__file__).with_name("stats.json")
WEBAPP_FILE = Path(__file__).with_name("webapp") / "index.html"
WIN_LINES = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


@dataclass
class Game:
    board: list[str]
    human: str
    bot: str
    mode: str = "bot"
    player_x_id: int | None = None
    player_o_id: int | None = None
    player_x_chat_id: int | None = None
    player_o_chat_id: int | None = None
    player_x_message_id: int | None = None
    player_o_message_id: int | None = None
    player_x_name: str = "Игрок ❎"
    player_o_name: str = "Игрок ⭕"
    turn: str = "X"
    bot_thinking: bool = False
    finished: bool = False


@dataclass
class WaitingPlayer:
    user_id: int
    chat_id: int
    message_id: int
    name: str


games: dict[int, Game] = {}
waiting_players: dict[int, WaitingPlayer] = {}
stats: dict[str, dict[str, dict[str, int]]] = {}
telegram_application: Application | None = None
app = FastAPI(title="Telegram Tic-Tac-Toe Bot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def empty_stats() -> dict[str, int]:
    return {"games": 0, "wins": 0, "losses": 0, "draws": 0}


def normalize_stats(raw_stats: dict) -> dict[str, dict[str, dict[str, int]]]:
    normalized = {}

    for user_id, user_stats in raw_stats.items():
        if not isinstance(user_stats, dict):
            continue

        normalized[str(user_id)] = {
            "bot": empty_stats(),
            "pvp": empty_stats(),
        }

        for mode in ("bot", "pvp"):
            mode_stats = user_stats.get(mode)
            if isinstance(mode_stats, dict):
                for key in ("games", "wins", "losses", "draws"):
                    value = mode_stats.get(key, 0)
                    normalized[str(user_id)][mode][key] = value if isinstance(value, int) else 0

        if any(key in user_stats for key in ("games", "wins", "losses", "draws")):
            for key in ("games", "wins", "losses", "draws"):
                value = user_stats.get(key, 0)
                normalized[str(user_id)]["bot"][key] += value if isinstance(value, int) else 0

    return normalized


def load_stats() -> dict[str, dict[str, dict[str, int]]]:
    if not STATS_FILE.exists():
        return {}

    try:
        data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return normalize_stats(data) if isinstance(data, dict) else {}


def save_stats() -> None:
    STATS_FILE.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_user_stats(user_id: int) -> dict[str, dict[str, int]]:
    user_stats = stats.setdefault(str(user_id), {})

    for mode in ("bot", "pvp"):
        user_stats.setdefault(mode, empty_stats())
        for key in ("games", "wins", "losses", "draws"):
            user_stats[mode].setdefault(key, 0)

    return user_stats


stats.update(load_stats())


def supabase_configured() -> bool:
    return bool(os.getenv(SUPABASE_URL_ENV_NAME) and os.getenv(SUPABASE_SERVICE_ROLE_KEY_ENV_NAME))


def supabase_headers() -> dict[str, str]:
    service_role_key = os.getenv(SUPABASE_SERVICE_ROLE_KEY_ENV_NAME)

    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def log_supabase_error(action: str, error: Exception) -> None:
    print(f"Supabase {action} failed: {type(error).__name__}: {error}", flush=True)


def local_add_user_result(user_id: int, mode: str, result: str) -> None:
    user_stats = get_user_stats(user_id)[mode]
    user_stats["games"] += 1
    user_stats[result] += 1
    save_stats()


async def supabase_get_stats(user_id: int) -> dict[str, dict[str, int]] | None:
    if not supabase_configured():
        return None

    url = f"{os.getenv(SUPABASE_URL_ENV_NAME).rstrip('/')}/rest/v1/user_stats"
    params = {"user_id": f"eq.{user_id}", "select": "stats"}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, headers=supabase_headers(), params=params)
        response.raise_for_status()
        rows = response.json()

    if not rows:
        return None

    return normalize_stats({str(user_id): rows[0].get("stats", {})}).get(str(user_id))


async def supabase_set_stats(user_id: int, user_stats: dict[str, dict[str, int]]) -> None:
    url = f"{os.getenv(SUPABASE_URL_ENV_NAME).rstrip('/')}/rest/v1/user_stats"
    payload = {"user_id": str(user_id), "stats": user_stats}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json=payload,
        )
        response.raise_for_status()


async def async_add_user_result(user_id: int, mode: str, result: str) -> None:
    if not supabase_configured():
        local_add_user_result(user_id, mode, result)
        return

    try:
        user_stats = await supabase_get_stats(user_id)

        if user_stats is None:
            user_stats = {"bot": empty_stats(), "pvp": empty_stats()}

        user_stats.setdefault(mode, empty_stats())
        user_stats[mode]["games"] += 1
        user_stats[mode][result] += 1
        await supabase_set_stats(user_id, user_stats)
    except Exception as error:
        log_supabase_error("write", error)
        local_add_user_result(user_id, mode, result)


async def get_stats_for_api(user_id: int) -> dict[str, dict[str, int]]:
    if supabase_configured():
        try:
            user_stats = await supabase_get_stats(user_id)
            if user_stats is not None:
                return user_stats
        except Exception as error:
            log_supabase_error("read", error)

    return get_user_stats(user_id)


def game_key(update: Update) -> int:
    return update.effective_user.id


def check_winner(board: list[str]) -> str | None:
    for a, b, c in WIN_LINES:
        if board[a] != EMPTY and board[a] == board[b] == board[c]:
            return board[a]

    if EMPTY not in board:
        return "draw"

    return None


def minimax(board: list[str], bot_turn: bool, human: str, bot: str) -> int:
    result = check_winner(board)

    if result == bot:
        return 1
    if result == human:
        return -1
    if result == "draw":
        return 0

    scores = []
    symbol = bot if bot_turn else human

    for index, cell in enumerate(board):
        if cell == EMPTY:
            board[index] = symbol
            scores.append(minimax(board, not bot_turn, human, bot))
            board[index] = EMPTY

    return max(scores) if bot_turn else min(scores)


def choose_bot_move(board: list[str], human: str, bot: str) -> int | None:
    moves = []

    for index, cell in enumerate(board):
        if cell == EMPTY:
            board[index] = bot
            score = minimax(board, False, human, bot)
            board[index] = EMPTY
            moves.append((score, index))

    if not moves:
        return None

    best_score = max(score for score, _ in moves)
    best_moves = [index for score, index in moves if score == best_score]
    weaker_moves = [index for score, index in moves if score < best_score]

    if weaker_moves and random.random() < BOT_MISTAKE_CHANCE:
        return random.choice(weaker_moves)

    return random.choice(best_moves)


def choose_mode_markup() -> InlineKeyboardMarkup:
    keyboard = []
    webapp_url = os.getenv(WEBAPP_URL_ENV_NAME)

    if webapp_url:
        keyboard.append([InlineKeyboardButton("Открыть приложение", web_app=WebAppInfo(webapp_url))])

    keyboard.extend(
        [
            [InlineKeyboardButton("Играть с ботом", callback_data="mode:bot")],
            [InlineKeyboardButton("Играть с другом", callback_data="mode:pvp")],
            [InlineKeyboardButton("Статистика", callback_data="stats")],
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def choose_side_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Играть за ❎", callback_data="side:bot:X"),
                InlineKeyboardButton("Играть за ⭕", callback_data="side:bot:O"),
            ],
            [InlineKeyboardButton("Случайно", callback_data="side:bot:random")],
            [InlineKeyboardButton("Статистика", callback_data="stats")],
        ]
    )


def board_markup(board: list[str]) -> InlineKeyboardMarkup:
    keyboard = []

    for row in range(3):
        buttons = []
        for col in range(3):
            index = row * 3 + col
            buttons.append(
                InlineKeyboardButton(symbol_text(board[index]), callback_data=f"move:{index}")
            )
        keyboard.append(buttons)

    keyboard.append(
        [
            InlineKeyboardButton("Новая игра", callback_data="new"),
            InlineKeyboardButton("Статистика", callback_data="stats"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def stats_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Новая игра", callback_data="new")],
        ]
    )


def waiting_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Новая игра", callback_data="new")],
            [InlineKeyboardButton("Статистика", callback_data="stats")],
        ]
    )


def symbol_text(symbol: str) -> str:
    return SYMBOL_EMOJI.get(symbol, symbol)


def status_text(game: Game) -> str:
    board = game.board
    result = check_winner(board)

    if result in ("X", "O"):
        if game.mode == "pvp":
            return f"Победил {player_name(game, result)}!"
        if result == game.human:
            return "Вы выиграли!"
        return "Бот выиграл!"
    if result == "draw":
        return "Ничья!"

    if game.mode == "pvp":
        return f"Ходит {player_name(game, game.turn)} ({symbol_text(game.turn)})."

    if game.bot_thinking:
        return "Бот думает..."

    return f"Ваш ход. Вы играете за {symbol_text(game.human)}."


def player_name(game: Game, symbol: str) -> str:
    return game.player_x_name if symbol == "X" else game.player_o_name


def player_symbol(game: Game, user_id: int) -> str | None:
    if user_id == game.player_x_id:
        return "X"
    if user_id == game.player_o_id:
        return "O"
    return None


def display_name(update: Update) -> str:
    user = update.effective_user
    return user.first_name or user.username or "Игрок"


def remove_user_from_waiting(user_id: int) -> None:
    waiting_players.pop(user_id, None)


def make_bot_game(human: str, user_id: int, user_name: str) -> Game:
    bot = "O" if human == "X" else "X"
    game = Game(board=[EMPTY] * 9, human=human, bot=bot, mode="bot")
    game.player_x_id = user_id if human == "X" else None
    game.player_o_id = user_id if human == "O" else None
    game.player_x_name = user_name if human == "X" else "Бот"
    game.player_o_name = user_name if human == "O" else "Бот"

    return game


def make_pvp_game(player_x: WaitingPlayer, player_o: WaitingPlayer) -> Game:
    return Game(
        board=[EMPTY] * 9,
        human="",
        bot="",
        mode="pvp",
        player_x_id=player_x.user_id,
        player_o_id=player_o.user_id,
        player_x_chat_id=player_x.chat_id,
        player_o_chat_id=player_o.chat_id,
        player_x_message_id=player_x.message_id,
        player_o_message_id=player_o.message_id,
        player_x_name=player_x.name,
        player_o_name=player_o.name,
    )


def game_text(game: Game) -> str:
    if game.mode == "pvp":
        return (
            "Крестики-нолики: игра с другом\n\n"
            f"{symbol_text('X')}: {game.player_x_name}\n"
            f"{symbol_text('O')}: {game.player_o_name}\n"
            f"{status_text(game)}"
        )

    return (
        "Крестики-нолики\n\n"
        f"Вы играете за {symbol_text(game.human)}, "
        f"бот играет за {symbol_text(game.bot)}.\n"
        f"{status_text(game)}"
    )


def add_user_result(user_id: int, mode: str, result: str) -> None:
    local_add_user_result(user_id, mode, result)


def record_result(user_id: int, game: Game) -> None:
    result = check_winner(game.board)

    if result is None or game.finished:
        return

    if game.mode == "pvp":
        if result == "draw":
            for player_id in (game.player_x_id, game.player_o_id):
                if player_id is not None:
                    add_user_result(player_id, "pvp", "draws")
        else:
            winner_id = game.player_x_id if result == "X" else game.player_o_id
            loser_id = game.player_o_id if result == "X" else game.player_x_id
            if winner_id is not None:
                add_user_result(winner_id, "pvp", "wins")
            if loser_id is not None:
                add_user_result(loser_id, "pvp", "losses")
    elif result == game.human:
        add_user_result(user_id, "bot", "wins")
    elif result == game.bot:
        add_user_result(user_id, "bot", "losses")
    else:
        add_user_result(user_id, "bot", "draws")

    game.finished = True
    save_stats()


async def async_record_result(user_id: int, game: Game) -> None:
    result = check_winner(game.board)

    if result is None or game.finished:
        return

    if game.mode == "pvp":
        if result == "draw":
            for player_id in (game.player_x_id, game.player_o_id):
                if player_id is not None:
                    await async_add_user_result(player_id, "pvp", "draws")
        else:
            winner_id = game.player_x_id if result == "X" else game.player_o_id
            loser_id = game.player_o_id if result == "X" else game.player_x_id
            if winner_id is not None:
                await async_add_user_result(winner_id, "pvp", "wins")
            if loser_id is not None:
                await async_add_user_result(loser_id, "pvp", "losses")
    elif result == game.human:
        await async_add_user_result(user_id, "bot", "wins")
    elif result == game.bot:
        await async_add_user_result(user_id, "bot", "losses")
    else:
        await async_add_user_result(user_id, "bot", "draws")

    game.finished = True


def stats_text(user_id: int) -> str:
    user_stats = get_user_stats(user_id)

    def section(title: str, mode: str) -> str:
        mode_stats = user_stats[mode]
        games_count = mode_stats["games"]
        wins = mode_stats["wins"]
        losses = mode_stats["losses"]
        draws = mode_stats["draws"]
        win_rate = wins / games_count * 100 if games_count else 0

        return (
            f"{title}\n"
            f"Игр: {games_count}\n"
            f"Побед: {wins}\n"
            f"Поражений: {losses}\n"
            f"Ничьих: {draws}\n"
            f"Процент побед: {win_rate:.1f}%"
        )

    return (
        "Ваша статистика\n\n"
        f"{section('Игра с ботом', 'bot')}\n\n"
        f"{section('Игра с другом', 'pvp')}"
    )


async def update_pvp_messages(context: ContextTypes.DEFAULT_TYPE, game: Game) -> None:
    for chat_id, message_id in (
        (game.player_x_chat_id, game.player_x_message_id),
        (game.player_o_chat_id, game.player_o_message_id),
    ):
        if chat_id is None or message_id is None:
            continue

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=game_text(game),
                reply_markup=board_markup(game.board),
            )
        except TelegramError:
            pass


async def start_pvp_matchmaking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    remove_user_from_waiting(user.id)

    current = WaitingPlayer(
        user_id=user.id,
        chat_id=update.effective_chat.id,
        message_id=query.message.message_id,
        name=display_name(update),
    )
    candidates = [player for player in waiting_players.values() if player.user_id != user.id]

    if not candidates:
        waiting_players[user.id] = current
        await query.edit_message_text(
            "Ищем соперника...\n\n"
            "Когда другой пользователь нажмёт «Играть с другом», бот соединит вас автоматически.",
            reply_markup=waiting_markup(),
        )
        return

    opponent = random.choice(candidates)
    remove_user_from_waiting(opponent.user_id)
    player_x, player_o = random.sample([current, opponent], 2)
    game = make_pvp_game(player_x, player_o)
    games[player_x.user_id] = game
    games[player_o.user_id] = game
    await update_pvp_messages(context, game)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_game(update, context)


async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    remove_user_from_waiting(update.effective_user.id)
    text = "Крестики-нолики\n\nВыберите режим игры:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=choose_mode_markup())
    else:
        await update.message.reply_text(text, reply_markup=choose_mode_markup())


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if supabase_configured():
        user_stats = await get_stats_for_api(update.effective_user.id)
        old_stats = stats.get(str(update.effective_user.id))
        stats[str(update.effective_user.id)] = user_stats
        text = stats_text(update.effective_user.id)
        if old_stats is None:
            stats.pop(str(update.effective_user.id), None)
        else:
            stats[str(update.effective_user.id)] = old_stats
    else:
        text = stats_text(update.effective_user.id)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=stats_markup())
    else:
        await update.message.reply_text(text, reply_markup=stats_markup())


async def open_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    webapp_url = os.getenv(WEBAPP_URL_ENV_NAME)

    if not webapp_url:
        await update.message.reply_text(
            "Ссылка на Telegram Mini App не настроена.\n\n"
            f"Укажите HTTPS-ссылку в переменной окружения {WEBAPP_URL_ENV_NAME}."
        )
        return

    await update.message.reply_text(
        "Откройте приложение с игрой:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Открыть приложение", web_app=WebAppInfo(webapp_url))]]
        ),
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if query.data == "new":
        await new_game(update, context)
        return

    if query.data == "stats":
        await query.answer()
        await show_stats(update, context)
        return

    if query.data.startswith("mode:"):
        await query.answer()
        mode = query.data.split(":", 1)[1]
        if mode == "pvp":
            await start_pvp_matchmaking(update, context)
            return

        await query.edit_message_text(
            "Выберите, за кого хотите играть:",
            reply_markup=choose_side_markup(),
        )
        return

    if query.data.startswith("side:"):
        await query.answer()
        _, mode, side = query.data.split(":", 2)
        if mode == "pvp":
            await start_pvp_matchmaking(update, context)
            return

        human = random.choice(["X", "O"]) if side == "random" else side
        user = update.effective_user
        game = make_bot_game(human, user.id, display_name(update))
        games[game_key(update)] = game
        await query.edit_message_text(game_text(game), reply_markup=board_markup(game.board))
        if game.bot == "X":
            game.bot_thinking = True
            await query.edit_message_text(game_text(game), reply_markup=board_markup(game.board))
            await asyncio.sleep(BOT_MOVE_DELAY_SECONDS)
            if games.get(game_key(update)) is not game:
                return
            bot_move = choose_bot_move(game.board, game.human, game.bot)
            if bot_move is not None:
                game.board[bot_move] = game.bot
            game.bot_thinking = False
            await query.edit_message_text(game_text(game), reply_markup=board_markup(game.board))
        return

    key = game_key(update)
    game = games.get(key)

    if game is None:
        await query.answer()
        await query.edit_message_text(
            "Сначала выберите режим игры:",
            reply_markup=choose_mode_markup(),
        )
        return

    board = game.board

    if check_winner(board) is not None:
        await query.answer()
        await async_record_result(update.effective_user.id, game)
        if game.mode == "pvp":
            await update_pvp_messages(context, game)
        else:
            await query.edit_message_text(game_text(game), reply_markup=board_markup(board))
        return

    index = int(query.data.split(":", 1)[1])

    if game.mode == "pvp":
        if None in (game.player_x_id, game.player_o_id):
            await query.answer("Сначала должен присоединиться второй игрок", show_alert=True)
            return

        symbol = player_symbol(game, update.effective_user.id)
        if symbol is None:
            await query.answer("Это не ваша игра", show_alert=True)
            return
        if symbol != game.turn:
            await query.answer("Сейчас ход другого игрока", show_alert=True)
            return

    if game.mode == "bot" and update.effective_user.id not in (game.player_x_id, game.player_o_id):
        await query.answer("Это не ваша игра", show_alert=True)
        return

    if game.mode == "bot" and game.bot_thinking:
        await query.answer("Подождите ход бота", show_alert=True)
        return

    if board[index] != EMPTY:
        await query.answer("Эта клетка уже занята", show_alert=True)
        return

    await query.answer()
    board[index] = game.turn if game.mode == "pvp" else game.human

    if game.mode == "pvp":
        if check_winner(board) is None:
            game.turn = "O" if game.turn == "X" else "X"
    elif check_winner(board) is None:
        game.bot_thinking = True
        await query.edit_message_text(game_text(game), reply_markup=board_markup(board))
        await asyncio.sleep(BOT_MOVE_DELAY_SECONDS)
        if games.get(game_key(update)) is not game:
            return
        bot_move = choose_bot_move(board, game.human, game.bot)
        if bot_move is not None:
            board[bot_move] = game.bot
        game.bot_thinking = False

    await async_record_result(update.effective_user.id, game)
    if game.mode == "pvp":
        await update_pvp_messages(context, game)
    else:
        await query.edit_message_text(game_text(game), reply_markup=board_markup(board))


def main() -> None:
    application = build_application()
    application.run_polling()


def build_application() -> Application:
    token = os.getenv(TOKEN_ENV_NAME)

    if not token:
        raise RuntimeError(f"Укажите токен бота в переменной окружения {TOKEN_ENV_NAME}")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_game))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("app", open_app))
    application.add_handler(CallbackQueryHandler(handle_button))
    return application


@app.on_event("startup")
async def startup() -> None:
    global telegram_application

    telegram_application = build_application()
    await telegram_application.initialize()
    await telegram_application.start()

    webhook_url = os.getenv(WEBHOOK_URL_ENV_NAME)
    if webhook_url:
        await telegram_application.bot.set_webhook(webhook_url)


@app.on_event("shutdown")
async def shutdown() -> None:
    if telegram_application is None:
        return

    await telegram_application.stop()
    await telegram_application.shutdown()


@app.get("/")
async def root() -> FileResponse:
    if not WEBAPP_FILE.exists():
        raise HTTPException(status_code=404, detail="Mini App file not found")

    return FileResponse(WEBAPP_FILE)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/diagnostics")
async def diagnostics() -> dict:
    result = {
        "supabase_url_set": bool(os.getenv(SUPABASE_URL_ENV_NAME)),
        "supabase_service_role_key_set": bool(os.getenv(SUPABASE_SERVICE_ROLE_KEY_ENV_NAME)),
        "supabase_anon_key_set": bool(os.getenv(SUPABASE_ANON_KEY_ENV_NAME)),
        "telegram_webhook_url_set": bool(os.getenv(WEBHOOK_URL_ENV_NAME)),
        "telegram_webapp_url_set": bool(os.getenv(WEBAPP_URL_ENV_NAME)),
        "supabase_check": None,
    }

    if not supabase_configured():
        result["supabase_check"] = {"ok": False, "error": "Supabase is not configured"}
        return result

    try:
        url = f"{os.getenv(SUPABASE_URL_ENV_NAME).rstrip('/')}/rest/v1/user_stats"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                url,
                headers=supabase_headers(),
                params={"select": "user_id", "limit": "1"},
            )

        result["supabase_check"] = {
            "ok": response.is_success,
            "status_code": response.status_code,
            "body_preview": response.text[:300] if not response.is_success else "",
        }
    except Exception as error:
        result["supabase_check"] = {
            "ok": False,
            "error_type": type(error).__name__,
            "error": str(error),
        }

    return result


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, bool]:
    if telegram_application is None:
        raise HTTPException(status_code=503, detail="Telegram application is not ready")

    data = await request.json()
    update = Update.de_json(data, telegram_application.bot)
    await telegram_application.process_update(update)
    return {"ok": True}


@app.get("/api/stats/{user_id}")
async def api_get_stats(user_id: int) -> dict[str, dict[str, int]]:
    return await get_stats_for_api(user_id)


@app.post("/api/stats/{user_id}/result")
async def api_add_result(user_id: int, request: Request) -> dict[str, dict[str, int]]:
    data = await request.json()
    mode = data.get("mode")
    result = data.get("result")

    if mode not in ("bot", "pvp"):
        raise HTTPException(status_code=400, detail="Invalid mode")

    allowed_results = {"bot": {"wins", "losses", "draws"}, "pvp": {"wins", "losses", "draws"}}
    if result not in allowed_results[mode]:
        raise HTTPException(status_code=400, detail="Invalid result")

    await async_add_user_result(user_id, mode, result)
    return await get_stats_for_api(user_id)


if __name__ == "__main__":
    main()
