import asyncio
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Update, WebAppInfo
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
WEBAPP_PVP_GAME_TTL_SECONDS = 6 * 60 * 60
DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = ("ru", "en")
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

TEXTS = {
    "ru": {
        "app_button": "Открыть приложение",
        "bot_name": "Бот",
        "player_name": "Игрок",
        "choose_language": "Выберите язык / Choose your language:",
        "language_changed": "Язык изменён на русский.",
        "main_menu": "Крестики-нолики\n\nВыберите режим игры:",
        "play_bot": "Играть с ботом",
        "play_friend": "Играть с другом",
        "stats": "Статистика",
        "settings": "Настройки",
        "settings_title": "Настройки\n\nВыберите язык:",
        "play_x": "Играть за ❎",
        "play_o": "Играть за ⭕",
        "random": "Случайно",
        "new_game": "Новая игра",
        "winner": "Победил {name}!",
        "you_won": "Вы выиграли!",
        "bot_won": "Бот выиграл!",
        "draw": "Ничья!",
        "turn": "Ходит {name} ({symbol}).",
        "bot_thinking": "Бот думает...",
        "your_turn": "Ваш ход. Вы играете за {symbol}.",
        "game_friend_title": "Крестики-нолики: игра с другом",
        "game_title": "Крестики-нолики",
        "bot_game_sides": "Вы играете за {human}, бот играет за {bot}.",
        "stats_title": "Ваша статистика",
        "stats_bot": "Игра с ботом",
        "stats_pvp": "Игра с другом",
        "stats_games": "Игр",
        "stats_wins": "Побед",
        "stats_losses": "Поражений",
        "stats_draws": "Ничьих",
        "stats_win_rate": "Процент побед",
        "waiting": "Ищем соперника...\n\nКогда другой пользователь нажмёт «Играть с другом» в боте или приложении, бот соединит вас автоматически.",
        "webapp_not_configured": "Ссылка на Telegram Mini App не настроена.\n\nУкажите HTTPS-ссылку в переменной окружения {env}.",
        "open_app_message": "Откройте приложение с игрой:",
        "choose_side": "Выберите, за кого хотите играть:",
        "choose_mode_first": "Сначала выберите режим игры:",
        "need_second_player": "Сначала должен присоединиться второй игрок",
        "not_your_game": "Это не ваша игра",
        "other_turn": "Сейчас ход другого игрока",
        "wait_bot": "Подождите ход бота",
        "cell_occupied": "Эта клетка уже занята",
        "token_required": "Укажите токен бота в переменной окружения {env}",
        "menu_button": "Приложение",
    },
    "en": {
        "app_button": "Open app",
        "bot_name": "Bot",
        "player_name": "Player",
        "choose_language": "Choose your language / Выберите язык:",
        "language_changed": "Language changed to English.",
        "main_menu": "Tic-Tac-Toe\n\nChoose game mode:",
        "play_bot": "Play with bot",
        "play_friend": "Play with a friend",
        "stats": "Stats",
        "settings": "Settings",
        "settings_title": "Settings\n\nChoose language:",
        "play_x": "Play as ❎",
        "play_o": "Play as ⭕",
        "random": "Random",
        "new_game": "New game",
        "winner": "{name} won!",
        "you_won": "You won!",
        "bot_won": "Bot won!",
        "draw": "Draw!",
        "turn": "{name} ({symbol}) to move.",
        "bot_thinking": "Bot is thinking...",
        "your_turn": "Your turn. You play as {symbol}.",
        "game_friend_title": "Tic-Tac-Toe: play with a friend",
        "game_title": "Tic-Tac-Toe",
        "bot_game_sides": "You play as {human}, bot plays as {bot}.",
        "stats_title": "Your stats",
        "stats_bot": "Game with bot",
        "stats_pvp": "Game with a friend",
        "stats_games": "Games",
        "stats_wins": "Wins",
        "stats_losses": "Losses",
        "stats_draws": "Draws",
        "stats_win_rate": "Win rate",
        "waiting": "Looking for an opponent...\n\nWhen another user taps “Play with a friend” in the bot or app, the bot will connect you automatically.",
        "webapp_not_configured": "Telegram Mini App URL is not configured.\n\nSet an HTTPS URL in the {env} environment variable.",
        "open_app_message": "Open the game app:",
        "choose_side": "Choose your side:",
        "choose_mode_first": "Choose game mode first:",
        "need_second_player": "The second player must join first",
        "not_your_game": "This is not your game",
        "other_turn": "It is the other player's turn",
        "wait_bot": "Wait for the bot move",
        "cell_occupied": "This cell is already occupied",
        "token_required": "Set the bot token in the {env} environment variable",
        "menu_button": "App",
    },
}


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
    webapp_game_id: str | None = None
    updated_at: float = 0.0


@dataclass
class WaitingPlayer:
    user_id: int
    chat_id: int | None
    message_id: int | None
    name: str
    source: str = "bot"
    webapp_game_id: str | None = None


games: dict[int, Game] = {}
waiting_players: dict[int, WaitingPlayer] = {}
webapp_pvp_games: dict[str, Game] = {}
stats: dict[str, dict] = {}
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


def normalize_stats(raw_stats: dict) -> dict[str, dict]:
    normalized = {}

    for user_id, user_stats in raw_stats.items():
        if not isinstance(user_stats, dict):
            continue

        normalized[str(user_id)] = {
            "bot": empty_stats(),
            "pvp": empty_stats(),
            "settings": {},
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

        settings = user_stats.get("settings")
        if isinstance(settings, dict) and settings.get("language") in SUPPORTED_LANGUAGES:
            normalized[str(user_id)]["settings"]["language"] = settings["language"]

    return normalized


def load_stats() -> dict[str, dict]:
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


def get_user_stats(user_id: int) -> dict:
    user_stats = stats.setdefault(str(user_id), {})

    for mode in ("bot", "pvp"):
        user_stats.setdefault(mode, empty_stats())
        for key in ("games", "wins", "losses", "draws"):
            user_stats[mode].setdefault(key, 0)

    user_stats.setdefault("settings", {})
    return user_stats


stats.update(load_stats())


def user_has_language(user_id: int) -> bool:
    return get_user_stats(user_id).get("settings", {}).get("language") in SUPPORTED_LANGUAGES


def user_language(user_id: int | None) -> str:
    if user_id is None:
        return DEFAULT_LANGUAGE

    language = get_user_stats(user_id).get("settings", {}).get("language")
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def set_user_language(user_id: int, language: str) -> None:
    if language not in SUPPORTED_LANGUAGES:
        return

    get_user_stats(user_id)["settings"]["language"] = language
    save_stats()


def text_for_language(language: str, key: str, **kwargs) -> str:
    return TEXTS.get(language, TEXTS[DEFAULT_LANGUAGE]).get(key, TEXTS[DEFAULT_LANGUAGE][key]).format(**kwargs)


def text_for_user(user_id: int | None, key: str, **kwargs) -> str:
    return text_for_language(user_language(user_id), key, **kwargs)


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


async def supabase_get_stats(user_id: int) -> dict | None:
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


async def supabase_set_stats(user_id: int, user_stats: dict) -> None:
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
            user_stats = get_user_stats(user_id)

        user_stats.setdefault(mode, empty_stats())
        user_stats[mode]["games"] += 1
        user_stats[mode][result] += 1
        await supabase_set_stats(user_id, user_stats)
    except Exception as error:
        log_supabase_error("write", error)
        local_add_user_result(user_id, mode, result)


async def get_stats_for_api(user_id: int) -> dict:
    if supabase_configured():
        try:
            user_stats = await supabase_get_stats(user_id)
            if user_stats is not None:
                return user_stats
        except Exception as error:
            log_supabase_error("read", error)

    return get_user_stats(user_id)


async def async_load_user_language(user_id: int) -> None:
    if user_has_language(user_id) or not supabase_configured():
        return

    try:
        user_stats = await supabase_get_stats(user_id)
    except Exception as error:
        log_supabase_error("read language", error)
        return

    language = (user_stats or {}).get("settings", {}).get("language")
    if language in SUPPORTED_LANGUAGES:
        get_user_stats(user_id)["settings"]["language"] = language


async def async_set_user_language(user_id: int, language: str) -> None:
    if language not in SUPPORTED_LANGUAGES:
        return

    set_user_language(user_id, language)

    if not supabase_configured():
        return

    try:
        user_stats = await supabase_get_stats(user_id)
        if user_stats is None:
            user_stats = get_user_stats(user_id)
        user_stats.setdefault("settings", {})["language"] = language
        await supabase_set_stats(user_id, user_stats)
    except Exception as error:
        log_supabase_error("write language", error)


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


def language_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Русский", callback_data="lang:ru"),
                InlineKeyboardButton("English", callback_data="lang:en"),
            ],
        ]
    )


def choose_mode_markup(user_id: int | None = None) -> InlineKeyboardMarkup:
    keyboard = []
    webapp_url = os.getenv(WEBAPP_URL_ENV_NAME)

    if webapp_url:
        keyboard.append(
            [InlineKeyboardButton(text_for_user(user_id, "app_button"), web_app=WebAppInfo(webapp_url))]
        )

    keyboard.extend(
        [
            [InlineKeyboardButton(text_for_user(user_id, "play_bot"), callback_data="mode:bot")],
            [InlineKeyboardButton(text_for_user(user_id, "play_friend"), callback_data="mode:pvp")],
            [
                InlineKeyboardButton(text_for_user(user_id, "stats"), callback_data="stats"),
                InlineKeyboardButton(text_for_user(user_id, "settings"), callback_data="settings"),
            ],
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def choose_side_markup(user_id: int | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text_for_user(user_id, "play_x"), callback_data="side:bot:X"),
                InlineKeyboardButton(text_for_user(user_id, "play_o"), callback_data="side:bot:O"),
            ],
            [InlineKeyboardButton(text_for_user(user_id, "random"), callback_data="side:bot:random")],
            [InlineKeyboardButton(text_for_user(user_id, "stats"), callback_data="stats")],
        ]
    )


def board_markup(board: list[str], user_id: int | None = None) -> InlineKeyboardMarkup:
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
            InlineKeyboardButton(text_for_user(user_id, "new_game"), callback_data="new"),
            InlineKeyboardButton(text_for_user(user_id, "stats"), callback_data="stats"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def stats_markup(user_id: int | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text_for_user(user_id, "new_game"), callback_data="new")],
            [InlineKeyboardButton(text_for_user(user_id, "settings"), callback_data="settings")],
        ]
    )


def waiting_markup(user_id: int | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text_for_user(user_id, "new_game"), callback_data="new")],
            [InlineKeyboardButton(text_for_user(user_id, "stats"), callback_data="stats")],
        ]
    )


def settings_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Русский", callback_data="lang:ru"),
                InlineKeyboardButton("English", callback_data="lang:en"),
            ],
        ]
    )


def symbol_text(symbol: str) -> str:
    return SYMBOL_EMOJI.get(symbol, symbol)


def status_text(game: Game, user_id: int | None = None) -> str:
    board = game.board
    result = check_winner(board)

    if result in ("X", "O"):
        if game.mode == "pvp":
            return text_for_user(user_id, "winner", name=player_name(game, result))
        if result == game.human:
            return text_for_user(user_id, "you_won")
        return text_for_user(user_id, "bot_won")
    if result == "draw":
        return text_for_user(user_id, "draw")

    if game.mode == "pvp":
        return text_for_user(
            user_id,
            "turn",
            name=player_name(game, game.turn),
            symbol=symbol_text(game.turn),
        )

    if game.bot_thinking:
        return text_for_user(user_id, "bot_thinking")

    return text_for_user(user_id, "your_turn", symbol=symbol_text(game.human))


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
    return user.first_name or user.username or text_for_user(user.id, "player_name")


def remove_user_from_waiting(user_id: int) -> None:
    waiting_player = waiting_players.pop(user_id, None)

    if waiting_player is None or waiting_player.webapp_game_id is None:
        return

    game = webapp_pvp_games.get(waiting_player.webapp_game_id)
    if game is not None and not webapp_pvp_has_two_players(game):
        webapp_pvp_games.pop(waiting_player.webapp_game_id, None)


def webapp_pvp_has_two_players(game: Game) -> bool:
    return game.player_x_id is not None and game.player_o_id is not None


def cleanup_webapp_pvp_games() -> None:
    now = time.time()
    stale_game_ids = [
        game_id
        for game_id, game in webapp_pvp_games.items()
        if now - game.updated_at > WEBAPP_PVP_GAME_TTL_SECONDS
    ]

    for game_id in stale_game_ids:
        stale_game = webapp_pvp_games.pop(game_id, None)
        if stale_game is None:
            continue

        for player_id in (stale_game.player_x_id, stale_game.player_o_id):
            if player_id is not None and games.get(player_id) is stale_game:
                games.pop(player_id, None)

    for user_id, waiting_player in list(waiting_players.items()):
        if waiting_player.webapp_game_id and waiting_player.webapp_game_id not in webapp_pvp_games:
            waiting_players.pop(user_id, None)


def parse_api_user_id(data: dict) -> int:
    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    if user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    return user_id


def parse_api_user_name(data: dict) -> str:
    name = data.get("name")

    if not isinstance(name, str):
        return "Player"

    name = name.strip()
    return name[:40] if name else "Player"


def webapp_pvp_state(game: Game, user_id: int) -> dict:
    result = check_winner(game.board)
    symbol = player_symbol(game, user_id)

    if not webapp_pvp_has_two_players(game):
        status = "waiting"
    elif result is None:
        status = "playing"
    else:
        status = "finished"

    return {
        "game_id": game.webapp_game_id,
        "status": status,
        "board": game.board,
        "turn": game.turn,
        "result": result,
        "your_symbol": symbol,
        "can_move": status == "playing" and symbol == game.turn,
        "players": {
            "X": {"id": game.player_x_id, "name": game.player_x_name},
            "O": {"id": game.player_o_id, "name": game.player_o_name},
        },
    }


def make_waiting_webapp_pvp_game(user_id: int, name: str) -> Game:
    now = time.time()
    game = Game(
        board=[EMPTY] * 9,
        human="",
        bot="",
        mode="pvp",
        webapp_game_id=uuid4().hex,
        updated_at=now,
    )
    symbol = random.choice(["X", "O"])

    if symbol == "X":
        game.player_x_id = user_id
        game.player_x_name = name
    else:
        game.player_o_id = user_id
        game.player_o_name = name

    return game


def fill_pvp_slot(game: Game, player: WaitingPlayer) -> None:
    if game.player_x_id is None:
        game.player_x_id = player.user_id
        game.player_x_chat_id = player.chat_id
        game.player_x_message_id = player.message_id
        game.player_x_name = player.name
    else:
        game.player_o_id = player.user_id
        game.player_o_chat_id = player.chat_id
        game.player_o_message_id = player.message_id
        game.player_o_name = player.name


def register_pvp_game(game: Game) -> None:
    if game.player_x_id is not None:
        games[game.player_x_id] = game
    if game.player_o_id is not None:
        games[game.player_o_id] = game
    if game.webapp_game_id is not None:
        webapp_pvp_games[game.webapp_game_id] = game


def complete_pvp_match(first: WaitingPlayer, second: WaitingPlayer) -> Game:
    game = None

    for player in (first, second):
        if player.webapp_game_id is None:
            continue

        waiting_game = webapp_pvp_games.get(player.webapp_game_id)
        if waiting_game is not None and not webapp_pvp_has_two_players(waiting_game):
            game = waiting_game
            break

    if game is None:
        player_x, player_o = random.sample([first, second], 2)
        game = make_pvp_game(player_x, player_o)
        game.webapp_game_id = first.webapp_game_id or second.webapp_game_id
    else:
        current_ids = {game.player_x_id, game.player_o_id}
        for player in (first, second):
            if player.user_id not in current_ids:
                fill_pvp_slot(game, player)

    game.updated_at = time.time()
    register_pvp_game(game)
    return game


def join_webapp_pvp_game(user_id: int, name: str) -> Game:
    cleanup_webapp_pvp_games()
    remove_user_from_waiting(user_id)
    current = WaitingPlayer(
        user_id=user_id,
        chat_id=None,
        message_id=None,
        name=name,
        source="webapp",
        webapp_game_id=uuid4().hex,
    )

    candidates = []
    for waiting_user_id, waiting_player in list(waiting_players.items()):
        if waiting_user_id == user_id:
            continue

        if waiting_player.webapp_game_id is not None:
            waiting_game = webapp_pvp_games.get(waiting_player.webapp_game_id)
            if waiting_game is None or webapp_pvp_has_two_players(waiting_game):
                waiting_players.pop(waiting_user_id, None)
                continue

        candidates.append(waiting_player)

    if candidates:
        opponent = random.choice(candidates)
        waiting_players.pop(opponent.user_id, None)
        return complete_pvp_match(opponent, current)

    game = make_waiting_webapp_pvp_game(user_id, name)
    current.webapp_game_id = game.webapp_game_id
    webapp_pvp_games[game.webapp_game_id] = game
    waiting_players[user_id] = current
    return game


def make_bot_game(human: str, user_id: int, user_name: str) -> Game:
    bot = "O" if human == "X" else "X"
    game = Game(board=[EMPTY] * 9, human=human, bot=bot, mode="bot")
    game.player_x_id = user_id if human == "X" else None
    game.player_o_id = user_id if human == "O" else None
    game.player_x_name = user_name if human == "X" else text_for_user(user_id, "bot_name")
    game.player_o_name = user_name if human == "O" else text_for_user(user_id, "bot_name")

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
        updated_at=time.time(),
    )


def game_text(game: Game, user_id: int | None = None) -> str:
    if game.mode == "pvp":
        return (
            f"{text_for_user(user_id, 'game_friend_title')}\n\n"
            f"{symbol_text('X')}: {game.player_x_name}\n"
            f"{symbol_text('O')}: {game.player_o_name}\n"
            f"{status_text(game, user_id)}"
        )

    return (
        f"{text_for_user(user_id, 'game_title')}\n\n"
        f"{text_for_user(user_id, 'bot_game_sides', human=symbol_text(game.human), bot=symbol_text(game.bot))}\n"
        f"{status_text(game, user_id)}"
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
            f"{text_for_user(user_id, 'stats_games')}: {games_count}\n"
            f"{text_for_user(user_id, 'stats_wins')}: {wins}\n"
            f"{text_for_user(user_id, 'stats_losses')}: {losses}\n"
            f"{text_for_user(user_id, 'stats_draws')}: {draws}\n"
            f"{text_for_user(user_id, 'stats_win_rate')}: {win_rate:.1f}%"
        )

    return (
        f"{text_for_user(user_id, 'stats_title')}\n\n"
        f"{section(text_for_user(user_id, 'stats_bot'), 'bot')}\n\n"
        f"{section(text_for_user(user_id, 'stats_pvp'), 'pvp')}"
    )


async def edit_pvp_messages(bot, game: Game) -> None:
    for user_id, chat_id, message_id in (
        (game.player_x_id, game.player_x_chat_id, game.player_x_message_id),
        (game.player_o_id, game.player_o_chat_id, game.player_o_message_id),
    ):
        if chat_id is None or message_id is None:
            continue

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=game_text(game, user_id),
                reply_markup=board_markup(game.board, user_id),
            )
        except TelegramError:
            pass


async def update_pvp_messages(context: ContextTypes.DEFAULT_TYPE, game: Game) -> None:
    await edit_pvp_messages(context.bot, game)


async def update_pvp_bot_messages(game: Game) -> None:
    if telegram_application is None:
        return

    await edit_pvp_messages(telegram_application.bot, game)


async def start_pvp_matchmaking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    await async_load_user_language(user.id)
    cleanup_webapp_pvp_games()
    remove_user_from_waiting(user.id)

    current = WaitingPlayer(
        user_id=user.id,
        chat_id=update.effective_chat.id,
        message_id=query.message.message_id,
        name=display_name(update),
    )
    candidates = []
    for waiting_user_id, waiting_player in list(waiting_players.items()):
        if waiting_user_id == user.id:
            continue

        if waiting_player.webapp_game_id is not None:
            waiting_game = webapp_pvp_games.get(waiting_player.webapp_game_id)
            if waiting_game is None or webapp_pvp_has_two_players(waiting_game):
                waiting_players.pop(waiting_user_id, None)
                continue

        candidates.append(waiting_player)

    if not candidates:
        waiting_players[user.id] = current
        await query.edit_message_text(
            text_for_user(user.id, "waiting"),
            reply_markup=waiting_markup(user.id),
        )
        return

    opponent = random.choice(candidates)
    waiting_players.pop(opponent.user_id, None)
    game = complete_pvp_match(opponent, current)
    await update_pvp_messages(context, game)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await async_load_user_language(update.effective_user.id)
    await configure_user_menu_button(context, update.effective_chat.id, update.effective_user.id)
    if not user_has_language(update.effective_user.id):
        await show_language_selection(update, context)
        return

    await new_game(update, context)


async def show_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = text_for_language(DEFAULT_LANGUAGE, "choose_language")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=language_markup())
    else:
        await update.message.reply_text(text, reply_markup=language_markup())


async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await async_load_user_language(update.effective_user.id)
    await configure_user_menu_button(context, update.effective_chat.id, update.effective_user.id)
    if not user_has_language(update.effective_user.id):
        await show_language_selection(update, context)
        return

    remove_user_from_waiting(update.effective_user.id)
    text = text_for_user(update.effective_user.id, "main_menu")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=choose_mode_markup(update.effective_user.id),
        )
    else:
        await update.message.reply_text(text, reply_markup=choose_mode_markup(update.effective_user.id))


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await async_load_user_language(update.effective_user.id)
    text = text_for_user(update.effective_user.id, "settings_title")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=settings_markup())
    else:
        await update.message.reply_text(text, reply_markup=settings_markup())


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await async_load_user_language(update.effective_user.id)
    if supabase_configured():
        user_stats = await get_stats_for_api(update.effective_user.id)
        local_settings = get_user_stats(update.effective_user.id).get("settings", {})
        stats[str(update.effective_user.id)] = user_stats
        if local_settings.get("language") in SUPPORTED_LANGUAGES:
            stats[str(update.effective_user.id)].setdefault("settings", {})["language"] = local_settings["language"]
        text = stats_text(update.effective_user.id)
    else:
        text = stats_text(update.effective_user.id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=stats_markup(update.effective_user.id),
        )
    else:
        await update.message.reply_text(text, reply_markup=stats_markup(update.effective_user.id))


async def open_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await async_load_user_language(update.effective_user.id)
    webapp_url = os.getenv(WEBAPP_URL_ENV_NAME)

    if not webapp_url:
        await update.message.reply_text(
            text_for_user(update.effective_user.id, "webapp_not_configured", env=WEBAPP_URL_ENV_NAME)
        )
        return

    await update.message.reply_text(
        text_for_user(update.effective_user.id, "open_app_message"),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text_for_user(update.effective_user.id, "app_button"),
                        web_app=WebAppInfo(webapp_url),
                    )
                ]
            ]
        ),
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    await async_load_user_language(user_id)

    if query.data.startswith("lang:"):
        language = query.data.split(":", 1)[1]
        await async_set_user_language(user_id, language)
        await configure_user_menu_button(context, update.effective_chat.id, user_id)
        await query.answer()
        await query.edit_message_text(
            f"{text_for_user(user_id, 'language_changed')}\n\n{text_for_user(user_id, 'main_menu')}",
            reply_markup=choose_mode_markup(user_id),
        )
        return

    if query.data == "new":
        await new_game(update, context)
        return

    if query.data == "settings":
        await show_settings(update, context)
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
            text_for_user(user_id, "choose_side"),
            reply_markup=choose_side_markup(user_id),
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
        await query.edit_message_text(
            game_text(game, user_id),
            reply_markup=board_markup(game.board, user_id),
        )
        if game.bot == "X":
            game.bot_thinking = True
            await query.edit_message_text(
                game_text(game, user_id),
                reply_markup=board_markup(game.board, user_id),
            )
            await asyncio.sleep(BOT_MOVE_DELAY_SECONDS)
            if games.get(game_key(update)) is not game:
                return
            bot_move = choose_bot_move(game.board, game.human, game.bot)
            if bot_move is not None:
                game.board[bot_move] = game.bot
            game.bot_thinking = False
            await query.edit_message_text(
                game_text(game, user_id),
                reply_markup=board_markup(game.board, user_id),
            )
        return

    key = game_key(update)
    game = games.get(key)

    if game is None:
        await query.answer()
        await query.edit_message_text(
            text_for_user(user_id, "choose_mode_first"),
            reply_markup=choose_mode_markup(user_id),
        )
        return

    board = game.board

    if check_winner(board) is not None:
        await query.answer()
        await async_record_result(update.effective_user.id, game)
        if game.mode == "pvp":
            await update_pvp_messages(context, game)
        else:
            await query.edit_message_text(game_text(game, user_id), reply_markup=board_markup(board, user_id))
        return

    index = int(query.data.split(":", 1)[1])

    if game.mode == "pvp":
        if None in (game.player_x_id, game.player_o_id):
            await query.answer(text_for_user(user_id, "need_second_player"), show_alert=True)
            return

        symbol = player_symbol(game, update.effective_user.id)
        if symbol is None:
            await query.answer(text_for_user(user_id, "not_your_game"), show_alert=True)
            return
        if symbol != game.turn:
            await query.answer(text_for_user(user_id, "other_turn"), show_alert=True)
            return

    if game.mode == "bot" and update.effective_user.id not in (game.player_x_id, game.player_o_id):
        await query.answer(text_for_user(user_id, "not_your_game"), show_alert=True)
        return

    if game.mode == "bot" and game.bot_thinking:
        await query.answer(text_for_user(user_id, "wait_bot"), show_alert=True)
        return

    if board[index] != EMPTY:
        await query.answer(text_for_user(user_id, "cell_occupied"), show_alert=True)
        return

    await query.answer()
    board[index] = game.turn if game.mode == "pvp" else game.human

    if game.mode == "pvp":
        game.updated_at = time.time()
        if check_winner(board) is None:
            game.turn = "O" if game.turn == "X" else "X"
    elif check_winner(board) is None:
        game.bot_thinking = True
        await query.edit_message_text(game_text(game, user_id), reply_markup=board_markup(board, user_id))
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
        await query.edit_message_text(game_text(game, user_id), reply_markup=board_markup(board, user_id))


async def configure_menu_button(application: Application) -> None:
    webapp_url = os.getenv(WEBAPP_URL_ENV_NAME)

    if not webapp_url:
        return

    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text_for_language(DEFAULT_LANGUAGE, "menu_button"),
                WebAppInfo(webapp_url),
            )
        )
    except TelegramError as error:
        print(f"Telegram menu button setup failed: {type(error).__name__}: {error}", flush=True)


async def configure_user_menu_button(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> None:
    webapp_url = os.getenv(WEBAPP_URL_ENV_NAME)

    if not webapp_url:
        return

    try:
        await context.bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(text_for_user(user_id, "menu_button"), WebAppInfo(webapp_url)),
        )
    except TelegramError:
        pass


def main() -> None:
    application = build_application()
    application.run_polling()


def build_application() -> Application:
    token = os.getenv(TOKEN_ENV_NAME)

    if not token:
        raise RuntimeError(text_for_language(DEFAULT_LANGUAGE, "token_required", env=TOKEN_ENV_NAME))

    application = Application.builder().token(token).post_init(configure_menu_button).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_game))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("settings", show_settings))
    application.add_handler(CommandHandler("app", open_app))
    application.add_handler(CallbackQueryHandler(handle_button))
    return application


@app.on_event("startup")
async def startup() -> None:
    global telegram_application

    telegram_application = build_application()
    await telegram_application.initialize()
    await telegram_application.start()
    await configure_menu_button(telegram_application)

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
async def api_get_stats(user_id: int) -> dict:
    return await get_stats_for_api(user_id)


@app.post("/api/stats/{user_id}/result")
async def api_add_result(user_id: int, request: Request) -> dict:
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


@app.post("/api/pvp/join")
async def api_pvp_join(request: Request) -> dict:
    data = await request.json()
    user_id = parse_api_user_id(data)
    name = parse_api_user_name(data)
    game = join_webapp_pvp_game(user_id, name)
    if webapp_pvp_has_two_players(game):
        await update_pvp_bot_messages(game)
    return webapp_pvp_state(game, user_id)


@app.get("/api/pvp/{game_id}")
async def api_pvp_get_game(game_id: str, user_id: int) -> dict:
    game = webapp_pvp_games.get(game_id)

    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    if player_symbol(game, user_id) is None:
        raise HTTPException(status_code=403, detail="This is not your game")

    game.updated_at = time.time()
    return webapp_pvp_state(game, user_id)


@app.post("/api/pvp/{game_id}/move")
async def api_pvp_move(game_id: str, request: Request) -> dict:
    game = webapp_pvp_games.get(game_id)

    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    data = await request.json()
    user_id = parse_api_user_id(data)
    symbol = player_symbol(game, user_id)

    if symbol is None:
        raise HTTPException(status_code=403, detail="This is not your game")

    if not webapp_pvp_has_two_players(game):
        raise HTTPException(status_code=400, detail="Waiting for opponent")

    if check_winner(game.board) is not None:
        await async_record_result(user_id, game)
        await update_pvp_bot_messages(game)
        return webapp_pvp_state(game, user_id)

    if symbol != game.turn:
        raise HTTPException(status_code=400, detail="It is not your turn")

    try:
        index = int(data.get("index"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid index")

    if index < 0 or index >= len(game.board):
        raise HTTPException(status_code=400, detail="Invalid index")

    if game.board[index] != EMPTY:
        raise HTTPException(status_code=400, detail="Cell is occupied")

    game.board[index] = symbol
    game.updated_at = time.time()

    if check_winner(game.board) is None:
        game.turn = "O" if game.turn == "X" else "X"
    else:
        await async_record_result(user_id, game)

    await update_pvp_bot_messages(game)

    return webapp_pvp_state(game, user_id)


if __name__ == "__main__":
    main()
