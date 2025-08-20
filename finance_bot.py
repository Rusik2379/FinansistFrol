import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
import sqlite3
from datetime import datetime
from calendar import month_name
import os
from pathlib import Path
from dotenv import load_dotenv

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Получаем абсолютный путь к директории скрипта
BASE_DIR = Path(__file__).parent
DB_PATH = os.path.join(BASE_DIR, 'finance.db')

# Состояния ConversationHandler
(
    MAIN_MENU,
    INCOME_AMOUNT, INCOME_CATEGORY, INCOME_CUSTOM_CATEGORY,
    EXPENSE_AMOUNT, EXPENSE_CATEGORY, EXPENSE_CUSTOM_CATEGORY,
    DEBT_AMOUNT, DEBT_PERSON, DEBT_TO_USER, DEBT_DESCRIPTION,
    STATS_MENU, STATS_TYPE, STATS_MONTH,
    SELECT_MONTH,
    DELETE_MENU, DELETE_INCOME, DELETE_EXPENSE, DELETE_DEBT,
    PROFILE_MENU
) = range(20)

# Категории и константы
INCOME_CATEGORIES = ['Зарплата', 'Подарок', 'Перевод', 'Другое']
EXPENSE_CATEGORIES = ['Жилье', 'Еда', 'Транспорт', 'Здоровье', 'Другое']
RUSSIAN_MONTHS = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
]
CURRENT_YEAR = datetime.now().year
RECORDS_PER_PAGE = 5

# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        first_name TEXT,
        last_name TEXT,
        registration_date TEXT,
        last_activity TEXT
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS incomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        amount REAL,
        category TEXT,
        date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        amount REAL,
        category TEXT,
        date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        from_username TEXT,
        to_user_id INTEGER,
        to_username TEXT,
        amount REAL,
        description TEXT,
        date TEXT,
        is_paid INTEGER DEFAULT 0,
        FOREIGN KEY (from_user_id) REFERENCES users (user_id),
        FOREIGN KEY (to_user_id) REFERENCES users (user_id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

# Клавиатуры
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [['Доходы', 'Расходы'], ['Долги', 'Статистика'], 
         ['Финансы', 'Удалить'], ['Мой профиль']],
        resize_keyboard=True
    )

def stats_menu_keyboard():
    return ReplyKeyboardMarkup(
        [['Доходы', 'Расходы'], ['Долги', 'Назад']],
        resize_keyboard=True
    )

def months_keyboard():
    keyboard = [RUSSIAN_MONTHS[i:i+3] for i in range(0, len(RUSSIAN_MONTHS), 3)]
    keyboard.append(['За все время', 'Назад'])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([['Назад']], resize_keyboard=True)

def delete_menu_keyboard():
    return ReplyKeyboardMarkup(
        [['Доходы', 'Расходы'], ['Долги', 'Назад']],
        resize_keyboard=True
    )

def profile_menu_keyboard():
    return ReplyKeyboardMarkup(
        [['Мои данные', 'Моя статистика'], ['Назад']],
        resize_keyboard=True
    )

# Регистрация и обновление пользователя
async def register_user(user):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    username = f"@{user.username.lower()}" if user.username else None
    now = datetime.now().isoformat()
    
    cursor.execute(
        '''INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, registration_date, last_activity) 
        VALUES (?, ?, ?, ?, ?, ?)''',
        (user.id, username, user.first_name, user.last_name, now, now)
    )
    
    cursor.execute(
        '''UPDATE users SET 
        username = ?,
        first_name = ?,
        last_name = ?,
        last_activity = ?
        WHERE user_id = ?''',
        (username, user.first_name, user.last_name, now, user.id)
    )
    
    conn.commit()
    conn.close()
    return username

# Основные команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    username = await register_user(user)
    
    welcome_msg = (
        f"Привет, {user.first_name}!\n"
        f"Твой юзернейм: {username or 'не установлен'}\n\n"
        "Я бот для учета финансов с системой аккаунтов.\n"
        "Теперь другие пользователи могут ссылаться на тебя через @юзернейм\n\n"
        "Чтобы установить/изменить юзернейм:\n"
        "1. Откройте настройки Telegram\n"
        "2. Перейдите в 'Изменить профиль'\n"
        "3. Установите 'Имя пользователя'"
    )
    
    await update.message.reply_text(
        welcome_msg,
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Действие отменено.',
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU

# Профиль пользователя
async def profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Меню профиля:',
        reply_markup=profile_menu_keyboard()
    )
    return PROFILE_MENU

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT username, first_name, last_name, registration_date 
        FROM users WHERE user_id = ?''',
        (user.id,)
    )
    profile = cursor.fetchone()
    
    if not profile:
        conn.close()
        await update.message.reply_text(
            'Профиль не найден! Начните с команды /start',
            reply_markup=main_menu_keyboard()
        )
        return MAIN_MENU
    
    username, first_name, last_name, reg_date = profile
    reg_date = datetime.fromisoformat(reg_date).strftime('%d.%m.%Y %H:%M')
    
    # Получаем статистику
    cursor.execute(
        '''SELECT SUM(amount) FROM incomes WHERE user_id = ?''',
        (user.id,)
    )
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute(
        '''SELECT SUM(amount) FROM expenses WHERE user_id = ?''',
        (user.id,)
    )
    total_expense = cursor.fetchone()[0] or 0
    
    cursor.execute(
        '''SELECT SUM(amount) FROM debts WHERE from_user_id = ? AND is_paid = 0''',
        (user.id,)
    )
    total_debts = cursor.fetchone()[0] or 0
    
    conn.close()
    
    profile_msg = (
        f"📌 Ваш профиль:\n"
        f"👤 Имя: {first_name} {last_name or ''}\n"
        f"📛 Юзернейм: {username or 'не установлен'}\n"
        f"🆔 ID: {user.id}\n"
        f"📅 Регистрация: {reg_date}\n\n"
        f"💰 Общие доходы: {total_income:.2f} руб.\n"
        f"💸 Общие расходы: {total_expense:.2f} руб.\n"
        f"🧾 Текущие долги: {total_debts:.2f} руб.\n\n"
        f"Чтобы другие пользователи могли ссылаться на вас, "
        f"установите username в настройках Telegram"
    )
    
    await update.message.reply_text(
        profile_msg,
        reply_markup=profile_menu_keyboard()
    )
    return PROFILE_MENU

async def find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "Укажите юзернейм после команды, например: /find @username",
            reply_markup=main_menu_keyboard()
        )
        return
    
    username = args[0].lower()
    if not username.startswith('@'):
        username = f"@{username}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT user_id, first_name, last_name, registration_date 
        FROM users WHERE username = ?''',
        (username,)
    )
    found_user = cursor.fetchone()
    
    if not found_user:
        conn.close()
        await update.message.reply_text(
            f"Пользователь {username} не найден в системе",
            reply_markup=main_menu_keyboard()
        )
        return
    
    user_id, first_name, last_name, reg_date = found_user
    reg_date = datetime.fromisoformat(reg_date).strftime('%d.%m.%Y')
    
    # Проверяем есть ли долги между пользователями
    cursor.execute(
        '''SELECT SUM(amount) FROM debts 
        WHERE from_user_id = ? AND to_user_id = ? AND is_paid = 0''',
        (user.id, user_id)
    )
    debts_to_user = cursor.fetchone()[0] or 0
    
    cursor.execute(
        '''SELECT SUM(amount) FROM debts 
        WHERE from_user_id = ? AND to_user_id = ? AND is_paid = 0''',
        (user_id, user.id)
    )
    debts_from_user = cursor.fetchone()[0] or 0
    
    conn.close()
    
    response_msg = (
        f"🔍 Найден пользователь:\n"
        f"👤 Имя: {first_name} {last_name or ''}\n"
        f"📛 Юзернейм: {username}\n"
        f"🆔 ID: {user_id}\n"
        f"📅 Регистрация: {reg_date}\n\n"
    )
    
    if debts_to_user > 0:
        response_msg += f"→ Вы должны ему: {debts_to_user:.2f} руб.\n"
    if debts_from_user > 0:
        response_msg += f"← Он должен вам: {debts_from_user:.2f} руб."
    
    if debts_to_user == 0 and debts_from_user == 0:
        response_msg += "Нет активных долгов между вами"
    
    await update.message.reply_text(
        response_msg,
        reply_markup=main_menu_keyboard()
    )

# Доходы
async def income_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Введите сумму дохода:',
        reply_markup=ReplyKeyboardRemove()
    )
    return INCOME_AMOUNT

async def income_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(',', '.'))
        if amount <= 0:
            await update.message.reply_text('Сумма должна быть положительной!')
            return INCOME_AMOUNT
            
        context.user_data['income_amount'] = amount
        await update.message.reply_text(
            'Выберите категорию:',
            reply_markup=ReplyKeyboardMarkup(
                [INCOME_CATEGORIES[i:i+2] for i in range(0, len(INCOME_CATEGORIES), 2)],
                resize_keyboard=True
            )
        )
        return INCOME_CATEGORY
    except ValueError:
        await update.message.reply_text('Введите корректную сумму (например: 1500 или 1500.50)')
        return INCOME_AMOUNT

async def income_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text
    if category not in INCOME_CATEGORIES:
        await update.message.reply_text('Пожалуйста, выберите категорию из предложенных.')
        return INCOME_CATEGORY
    
    if category == 'Другое':
        await update.message.reply_text(
            'Введите название категории:',
            reply_markup=ReplyKeyboardRemove()
        )
        return INCOME_CUSTOM_CATEGORY
    
    await save_income(update, context, category)
    return MAIN_MENU

async def income_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text
    await save_income(update, context, category)
    return MAIN_MENU

async def save_income(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    amount = context.user_data['income_amount']
    user = update.message.from_user
    username = f"@{user.username.lower()}" if user.username else None
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO incomes 
        (user_id, username, amount, category, date) 
        VALUES (?, ?, ?, ?, ?)''',
        (user.id, username, amount, category, current_date)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f'✅ Доход {amount:.2f} руб. ({category}) от {current_date[:10]} добавлен!',
        reply_markup=main_menu_keyboard()
    )

# Расходы
async def expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Введите сумму расхода:',
        reply_markup=ReplyKeyboardRemove()
    )
    return EXPENSE_AMOUNT

async def expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(',', '.'))
        if amount <= 0:
            await update.message.reply_text('Сумма должна быть положительной!')
            return EXPENSE_AMOUNT
            
        context.user_data['expense_amount'] = amount
        await update.message.reply_text(
            'Выберите категориу:',
            reply_markup=ReplyKeyboardMarkup(
                [EXPENSE_CATEGORIES[i:i+2] for i in range(0, len(EXPENSE_CATEGORIES), 2)],
                resize_keyboard=True
            )
        )
        return EXPENSE_CATEGORY
    except ValueError:
        await update.message.reply_text('Введите корректную сумму (например: 1500 или 1500.50)')
        return EXPENSE_AMOUNT

async def expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text
    if category not in EXPENSE_CATEGORIES:
        await update.message.reply_text('Пожалуйста, выберите категорию из предложенных.')
        return EXPENSE_CATEGORY
    
    if category == 'Другое':
        await update.message.reply_text(
            'Введите название категории:',
            reply_markup=ReplyKeyboardRemove()
        )
        return EXPENSE_CUSTOM_CATEGORY
    
    await save_expense(update, context, category)
    return MAIN_MENU

async def expense_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text
    await save_expense(update, context, category)
    return MAIN_MENU

async def save_expense(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    amount = context.user_data['expense_amount']
    user = update.message.from_user
    username = f"@{user.username.lower()}" if user.username else None
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO expenses 
        (user_id, username, amount, category, date) 
        VALUES (?, ?, ?, ?, ?)''',
        (user.id, username, amount, category, current_date)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f'✅ Расход {amount:.2f} руб. ({category}) от {current_date[:10]} добавлен!',
        reply_markup=main_menu_keyboard()
    )

# Долги
async def debt_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Введите сумму долга:',
        reply_markup=ReplyKeyboardRemove()
    )
    return DEBT_AMOUNT

async def debt_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(',', '.'))
        if amount <= 0:
            await update.message.reply_text('Сумма должна быть положительной!')
            return DEBT_AMOUNT
            
        context.user_data['debt_amount'] = amount
        await update.message.reply_text(
            'Введите имя должника или его @юзернейм:',
            reply_markup=back_keyboard()
        )
        return DEBT_PERSON
    except ValueError:
        await update.message.reply_text('Введите корректную сумму (например: 1500 или 1500.50)')
        return DEBT_AMOUNT

async def debt_person(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    person = update.message.text
    
    if person.startswith('@'):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, first_name FROM users WHERE username = ?",
            (person.lower(),)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user:
            context.user_data['debt_to_user_id'] = user[0]
            context.user_data['debt_to_username'] = person.lower()
            context.user_data['debt_to_name'] = user[1]
            await update.message.reply_text(
                f"Долг будет записан на пользователя {user[1]} ({person})\n"
                "Введите описание долга:",
                reply_markup=back_keyboard()
            )
            return DEBT_DESCRIPTION
    
    context.user_data['debt_person'] = person
    await update.message.reply_text(
        "Введите описание долга:",
        reply_markup=back_keyboard()
    )
    return DEBT_DESCRIPTION

async def save_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text
    amount = context.user_data['debt_amount']
    user = update.message.from_user
    username = f"@{user.username.lower()}" if user.username else None
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if 'debt_to_user_id' in context.user_data:
        cursor.execute(
            '''INSERT INTO debts 
            (from_user_id, from_username, to_user_id, to_username, 
             amount, description, date) 
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user.id, username, 
             context.user_data['debt_to_user_id'], context.user_data['debt_to_username'],
             amount, description, current_date)
        )
        person_info = context.user_data['debt_to_name']
    else:
        cursor.execute(
            '''INSERT INTO debts 
            (from_user_id, from_username, to_username, amount, description, date) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (user.id, username, context.user_data['debt_person'], 
             amount, description, current_date)
        )
        person_info = context.user_data['debt_person']
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f'✅ Долг {amount:.2f} руб. ({description})\n'
        f'Для: {person_info}\n'
        f'Успешно добавлен!',
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU

# Статистика
async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Выберите тип статистики:',
        reply_markup=stats_menu_keyboard()
    )
    return STATS_MENU

async def stats_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    stats_type = update.message.text
    if stats_type not in ['Доходы', 'Расходы', 'Долги']:
        await update.message.reply_text('Пожалуйста, выберите тип из предложенных.')
        return STATS_MENU
    
    context.user_data['stats_type'] = stats_type
    await update.message.reply_text(
        'Выберите месяц:',
        reply_markup=months_keyboard()
    )
    return STATS_MONTH

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_month = update.message.text
    if selected_month == 'Назад':
        return await stats_menu(update, context)
    
    stats_type = context.user_data['stats_type']
    user = update.message.from_user
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if selected_month == 'За все время':
        if stats_type == 'Доходы':
            cursor.execute(
                '''SELECT amount, category, date FROM incomes 
                WHERE user_id = ? ORDER BY date DESC''',
                (user.id,)
            )
        elif stats_type == 'Расходы':
            cursor.execute(
                '''SELECT amount, category, date FROM expenses 
                WHERE user_id = ? ORDER BY date DESC''',
                (user.id,)
            )
        else:
            cursor.execute(
                '''SELECT amount, to_username, description, date 
                FROM debts WHERE from_user_id = ? ORDER BY date DESC''',
                (user.id,)
            )
        period = "за все время"
    else:
        month_num = RUSSIAN_MONTHS.index(selected_month) + 1
        start_date = f"{CURRENT_YEAR}-{month_num:02d}-01"
        end_date = f"{CURRENT_YEAR}-{month_num+1:02d}-01" if month_num < 12 else f"{CURRENT_YEAR}-12-31"
        
        if stats_type == 'Доходы':
            cursor.execute(
                '''SELECT amount, category, date FROM incomes 
                WHERE user_id = ? AND date >= ? AND date < ? 
                ORDER BY date DESC''',
                (user.id, start_date, end_date)
            )
        elif stats_type == 'Расходы':
            cursor.execute(
                '''SELECT amount, category, date FROM expenses 
                WHERE user_id = ? AND date >= ? AND date < ? 
                ORDER BY date DESC''',
                (user.id, start_date, end_date)
            )
        else:
            cursor.execute(
                '''SELECT amount, to_username, description, date 
                FROM debts WHERE from_user_id = ? 
                AND date >= ? AND date < ? 
                ORDER BY date DESC''',
                (user.id, start_date, end_date)
            )
        period = f"за {selected_month.lower()} {CURRENT_YEAR}"
    
    records = cursor.fetchall()
    
    # Получаем сумму
    if selected_month == 'За все время':
        if stats_type == 'Доходы':
            cursor.execute(
                "SELECT SUM(amount) FROM incomes WHERE user_id = ?",
                (user.id,)
            )
        elif stats_type == 'Расходы':
            cursor.execute(
                "SELECT SUM(amount) FROM expenses WHERE user_id = ?",
                (user.id,)
            )
        else:
            cursor.execute(
                "SELECT SUM(amount) FROM debts WHERE from_user_id = ?",
                (user.id,)
            )
    else:
        if stats_type == 'Доходы':
            cursor.execute(
                '''SELECT SUM(amount) FROM incomes 
                WHERE user_id = ? AND date >= ? AND date < ?''',
                (user.id, start_date, end_date)
            )
        elif stats_type == 'Расходы':
            cursor.execute(
                '''SELECT SUM(amount) FROM expenses 
                WHERE user_id = ? AND date >= ? AND date < ?''',
                (user.id, start_date, end_date)
            )
        else:
            cursor.execute(
                '''SELECT SUM(amount) FROM debts 
                WHERE from_user_id = ? AND date >= ? AND date < ?''',
                (user.id, start_date, end_date)
            )
    
    total = cursor.fetchone()[0] or 0
    conn.close()
    
    if not records:
        await update.message.reply_text(
            f'Нет данных {stats_type.lower()} {period}.',
            reply_markup=stats_menu_keyboard()
        )
        return STATS_MENU
        
    message = f"📊 {stats_type} {period}:\n\n"
    
    if stats_type == 'Доходы':
        for amount, category, date in records:
            date_str = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
            message += f"• {amount:.2f} руб. ({category}) - {date_str}\n"
    elif stats_type == 'Расходы':
        for amount, category, date in records:
            date_str = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
            message += f"• {amount:.2f} руб. ({category}) - {date_str}\n"
    else:
        for amount, to_user, description, date in records:
            date_str = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
            message += f"• {amount:.2f} руб. для {to_user or description} - {date_str}\n"
    
    message += f"\n💰 Итого: {total:.2f} руб."
    
    # Разбиваем сообщение на части, если оно слишком длинное
    max_length = 4000
    if len(message) > max_length:
        parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
        for part in parts[:-1]:
            await update.message.reply_text(part)
        await update.message.reply_text(
            parts[-1],
            reply_markup=stats_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=stats_menu_keyboard()
        )
    
    return STATS_MENU

# Финансы (краткие итоги)
async def show_finances_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Выберите месяц для просмотра статистики:',
        reply_markup=months_keyboard()
    )
    return SELECT_MONTH

async def show_finances(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_month = update.message.text
    user = update.message.from_user
    
    if selected_month == 'Назад':
        await update.message.reply_text(
            'Отменено.',
            reply_markup=main_menu_keyboard()
        )
        return MAIN_MENU
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if selected_month == 'За все время':
        income_query = "SELECT SUM(amount) FROM incomes WHERE user_id = ?"
        expense_query = "SELECT SUM(amount) FROM expenses WHERE user_id = ?"
        debt_query = "SELECT SUM(amount) FROM debts WHERE from_user_id = ? AND is_paid = 0"
        params = (user.id,)
        period = "за все время"
    else:
        month_num = RUSSIAN_MONTHS.index(selected_month) + 1
        start_date = f"{CURRENT_YEAR}-{month_num:02d}-01"
        end_date = f"{CURRENT_YEAR}-{month_num+1:02d}-01" if month_num < 12 else f"{CURRENT_YEAR}-12-31"
        
        income_query = """
            SELECT SUM(amount) FROM incomes 
            WHERE user_id = ? AND date >= ? AND date < ?
        """
        expense_query = """
            SELECT SUM(amount) FROM expenses 
            WHERE user_id = ? AND date >= ? AND date < ?
        """
        debt_query = """
            SELECT SUM(amount) FROM debts 
            WHERE from_user_id = ? AND is_paid = 0 AND date >= ? AND date < ?
        """
        params = (user.id, start_date, end_date)
        period = f"за {selected_month.lower()} {CURRENT_YEAR}"
    
    cursor.execute(income_query, params)
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute(expense_query, params)
    total_expense = cursor.fetchone()[0] or 0
    
    cursor.execute(debt_query, params)
    total_debts = cursor.fetchone()[0] or 0
    
    conn.close()
    
    await update.message.reply_text(
        f'📊 <b>Финансы {period}</b>\n\n'
        f'💰 Доходы: {total_income:.2f} руб.\n'
        f'💸 Расходы: {total_expense:.2f} руб.\n'
        f'📉 Баланс: {total_income - total_expense:.2f} руб.\n'
        f'🧾 Долги: {total_debts:.2f} руб.',
        parse_mode='HTML',
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU

# Удаление записей
async def delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Что вы хотите удалить?',
        reply_markup=delete_menu_keyboard()
    )
    return DELETE_MENU

async def delete_incomes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT id, amount, category, date FROM incomes 
        WHERE user_id = ? ORDER BY date DESC LIMIT ?''',
        (user.id, RECORDS_PER_PAGE)
    )
    incomes = cursor.fetchall()
    conn.close()
    
    if not incomes:
        await update.message.reply_text(
            'Нет доходов для удаления.',
            reply_markup=delete_menu_keyboard()
        )
        return DELETE_MENU
    
    keyboard = []
    for income in incomes:
        id, amount, category, date = income
        date_str = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
        text = f"{amount} руб. ({category}) {date_str}"
        keyboard.append([f"Удалить доход #{id}: {text}"])
    
    keyboard.append(['Назад'])
    
    await update.message.reply_text(
        'Выберите доход для удаления:',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DELETE_INCOME

async def delete_income_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == 'Назад':
        return await delete_menu(update, context)
    
    try:
        income_id = int(text.split('#')[1].split(':')[0])
    except (IndexError, ValueError):
        await update.message.reply_text(
            'Ошибка формата. Попробуйте еще раз.',
            reply_markup=back_keyboard()
        )
        return DELETE_INCOME
    
    user = update.message.from_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'DELETE FROM incomes WHERE id = ? AND user_id = ?',
        (income_id, user.id)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted > 0:
        await update.message.reply_text(
            'Доход успешно удален!',
            reply_markup=delete_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            'Не удалось удалить доход. Возможно, он уже был удален.',
            reply_markup=delete_menu_keyboard()
        )
    
    return DELETE_MENU

async def delete_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT id, amount, category, date FROM expenses 
        WHERE user_id = ? ORDER BY date DESC LIMIT ?''',
        (user.id, RECORDS_PER_PAGE)
    )
    expenses = cursor.fetchall()
    conn.close()
    
    if not expenses:
        await update.message.reply_text(
            'Нет расходов для удаления.',
            reply_markup=delete_menu_keyboard()
        )
        return DELETE_MENU
    
    keyboard = []
    for expense in expenses:
        id, amount, category, date = expense
        date_str = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
        text = f"{amount} руб. ({category}) {date_str}"
        keyboard.append([f"Удалить расход #{id}: {text}"])
    
    keyboard.append(['Назад'])
    
    await update.message.reply_text(
        'Выберите расход для удаления:',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DELETE_EXPENSE

async def delete_expense_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == 'Назад':
        return await delete_menu(update, context)
    
    try:
        expense_id = int(text.split('#')[1].split(':')[0])
    except (IndexError, ValueError):
        await update.message.reply_text(
            'Ошибка формата. Попробуйте еще раз.',
            reply_markup=back_keyboard()
        )
        return DELETE_EXPENSE
    
    user = update.message.from_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'DELETE FROM expenses WHERE id = ? AND user_id = ?',
        (expense_id, user.id)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted > 0:
        await update.message.reply_text(
            'Расход успешно удален!',
            reply_markup=delete_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            'Не удалось удалить расход. Возможно, он уже был удален.',
            reply_markup=delete_menu_keyboard()
        )
    
    return DELETE_MENU

async def delete_debts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT id, amount, to_username, description, date FROM debts 
        WHERE from_user_id = ? ORDER BY date DESC LIMIT ?''',
        (user.id, RECORDS_PER_PAGE)
    )
    debts = cursor.fetchall()
    conn.close()
    
    if not debts:
        await update.message.reply_text(
            'Нет долгов для удаления.',
            reply_markup=delete_menu_keyboard()
        )
        return DELETE_MENU
    
    keyboard = []
    for debt in debts:
        id, amount, to_user, description, date = debt
        date_str = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
        text = f"{amount} руб. ({to_user or description}) {date_str}"
        keyboard.append([f"Удалить долг #{id}: {text}"])
    
    keyboard.append(['Назад'])
    
    await update.message.reply_text(
        'Выберите долг для удаления:',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DELETE_DEBT

async def delete_debt_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == 'Назад':
        return await delete_menu(update, context)
    
    try:
        debt_id = int(text.split('#')[1].split(':')[0])
    except (IndexError, ValueError):
        await update.message.reply_text(
            'Ошибка формата. Попробуйте еще раз.',
            reply_markup=back_keyboard()
        )
        return DELETE_DEBT
    
    user = update.message.from_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'DELETE FROM debts WHERE id = ? AND from_user_id = ?',
        (debt_id, user.id)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted > 0:
        await update.message.reply_text(
            'Долг успешно удален!',
            reply_markup=delete_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            'Не удалось удалить долг. Возможно, он уже был удален.',
            reply_markup=delete_menu_keyboard()
        )
    
    return DELETE_MENU

# Запуск бота
def main() -> None:
    # Загружаем переменные из файла .env
    load_dotenv()
    
    # Получаем токен из переменных окружения
    token = os.getenv('BOT_TOKEN')
    if token is None:
        raise ValueError("Токен бота не найден! Проверьте файл .env")
    
    logger.info("Запуск бота...")
    
    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex('^Доходы$'), income_start),
                MessageHandler(filters.Regex('^Расходы$'), expense_start),
                MessageHandler(filters.Regex('^Долги$'), debt_start),
                MessageHandler(filters.Regex('^Статистика$'), stats_menu),
                MessageHandler(filters.Regex('^Финансы$'), show_finances_start),
                MessageHandler(filters.Regex('^Удалить$'), delete_menu),
                MessageHandler(filters.Regex('^Мой профиль$'), profile_menu),
            ],
            PROFILE_MENU: [
                MessageHandler(filters.Regex('^Мои данные$'), show_profile),
                MessageHandler(filters.Regex('^Назад$'), cancel),
            ],
            INCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, income_amount)],
            INCOME_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, income_category)],
            INCOME_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, income_custom_category)],
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)],
            EXPENSE_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_custom_category)],
            DEBT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amount)],
            DEBT_PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_person)],
            DEBT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_debt)],
            STATS_MENU: [
                MessageHandler(filters.Regex('^Доходы$'), stats_type),
                MessageHandler(filters.Regex('^Расходы$'), stats_type),
                MessageHandler(filters.Regex('^Долги$'), stats_type),
                MessageHandler(filters.Regex('^Назад$'), cancel),
            ],
            STATS_MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_stats)],
            SELECT_MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_finances)],
            DELETE_MENU: [
                MessageHandler(filters.Regex('^Доходы$'), delete_incomes),
                MessageHandler(filters.Regex('^Расходы$'), delete_expenses),
                MessageHandler(filters.Regex('^Долги$'), delete_debts),
                MessageHandler(filters.Regex('^Назад$'), cancel),
            ],
            DELETE_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_income_record)],
            DELETE_EXPENSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_expense_record)],
            DELETE_DEBT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_debt_record)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("find", find_user))
    
    # Запускаем бота с обработкой ошибок
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # Игнорировать сообщения, отправленные пока бот был offline
        close_loop=False
    )

if __name__ == '__main__':
    main()