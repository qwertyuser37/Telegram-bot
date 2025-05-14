# Импорт фреймворков
import asyncio
import requests
import datetime, zoneinfo
import math
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Инициализация токена бота и объектов диспетчера и хранилища состояний
API_TOKEN = 'TOKEN'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher()

# Глобальные переменные для хранения сообщений, клавиатур и данных пользователя
forecast_message = ""
weather_message = ""
keyboard = None
user_reminders = {}
user_languages = {}
user_reminder_times = {}
user_states = {}

# Словарь со всеми сообщениями Telegram бота на русском и на английском языках
translations = {
    'start': {
        'ru': "Данный бот показывает погоду. Укажи город",
        'en': "This bot shows the weather. Please specify the city"
    },
    'settings_question': {
        'ru': "На какое время выставить напоминание о погоде в формате xx:xx?",
        'en': "What time would you like to set the weather reminder in the format hh:mm?"
    },
    'city_check': {
        'ru': "Проверь название города",
        'en': "Check the city name"
    },
    'data_error': {
        'ru': "Ошибка при получении данных о погоде",
        'en': "Error while fetching weather data"
    },
    'reminder_set': {
        'ru': "Теперь сообщение будет приходить каждый день в {time}",
        'en': "Now the message will come every day at {time}"
    },
    'weather_interest': {
        'ru': "Интересует ли вас погода?",
        'en': "Are you interested in the weather?"
    },
    'word': {
        'ru': "Да",
        'en': "Yes"
    },
    'invalid_time_format': {
        'ru': "Неверный формат времени. Пожалуйста, используйте формат hh:mm.",
        'en': "Invalid time format. Please use hh:mm format."
    }
}

# Определение состояний для FSM (машины состояний)
class EchoStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_message = State()
# Запуск Telegram бота
@dp.message(Command('start'))
async def first_message(message: types.Message):
    language = user_languages.get(message.from_user.id, 'ru')
    await message.reply(translations['start'][language])
# Настройка напоминаний
@dp.message(Command('settings'))
async def start_command(message: types.Message):
    language = user_languages.get(message.from_user.id, 'ru')
    user_states[message.from_user.id] = EchoStates.waiting_for_message
    await message.answer(translations['settings_question'][language])
# Английский язык
@dp.message(Command('en'))
async def set_language_en(message: types.Message):
    user_id = message.from_user.id
    user_languages[user_id] = 'en'
    await message.reply("You choose English language.")
# Русский язык
@dp.message(Command('ru'))
async def set_language_ru(message: types.Message):
    user_id = message.from_user.id
    user_languages[user_id] = 'ru'
    await message.reply("Ты выбрал русский язык")
# Функция set_reminder_time, нужная для обработки сообщения с временем напоминания
@dp.message(lambda message: user_states.get(message.from_user.id) == EchoStates.waiting_for_message)
async def set_reminder_time(message: types.Message):
    user_id = message.from_user.id
    language = user_languages.get(user_id, 'ru')
    time_input = message.text.strip()
    
    try:
        hour, minute = map(int, time_input.split(':'))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
        user_reminder_times[user_id] = time_input
        await message.reply(translations['reminder_set'][language].format(time=time_input))
        asyncio.create_task(send_daily_reminder(user_id, hour, minute))
        del user_states[user_id]
        
    except ValueError:
        await message.reply(translations['invalid_time_format'][language])

async def send_daily_reminder(user_id, hour, minute):
    while True:
        now = datetime.datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now > target_time:
            target_time += datetime.timedelta(days=1)
        wait_time = (target_time - now).total_seconds()
        await asyncio.sleep(wait_time)
        language = user_languages.get(user_id, 'ru')
        await bot.send_message(user_id, translations['weather_interest'][language])

@dp.message(F.text)
async def weather(message: types.Message):
    global weather_message, keyboard, forecast_message
    city = message.text
    user_id = message.from_user.id
    language = user_languages.get(user_id, 'ru')
    try:
        response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&lang=ru&units=metric&appid=API")
        data = response.json()
        if response.status_code != 200:
            await message.reply(translations['city_check'][language])
            return
    except Exception as e:
        await message.reply(translations['data_error'][language])
        return

    code_ru_en = {
        "Clear": ("Ясно ☀️", "Clear ☀️"),
        "Clouds": ("Облачно ☁️", "Cloudy ☁️"),
        "Rain": ("Дождь 🌧️", "Rain 🌧️"),
        "Drizzle": ("Дождь 🌦️", "Drizzle 🌦️"),
        "Thunderstorm": ("Гроза ⛈️", "Thunderstorm ⛈️"),
        "Snow": ("Снег ❄️", "Snow ❄️"),
        "Mist": ("Туман 🌫️", "Mist 🌫️")
    }
    lat = data['coord']['lat']
    lon = data['coord']['lon']
    timezone_offset = data.get('timezone', 0)
    def get_local_time(timestamp, offset_seconds):
        # Получаем время в UTC с timezone-aware объектом
        utc_time = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        # Добавляем смещение для получения локального времени
        local_time = utc_time + datetime.timedelta(seconds=offset_seconds)
        return local_time
    weather_message = f"Прогноз погоды в городе: {city}\n" if language == 'ru' else f"Weather forecast in the city: {city}\n"
    weather = data
    temp = weather["main"]["temp"]
    temp1 = weather["main"]["feels_like"]
    humidity = weather["main"]["humidity"]
    pressure = weather["main"]["pressure"]
    wind = weather["wind"]["speed"]
    sunrise_utc = data["sys"]["sunrise"]
    sunset_utc = data["sys"]["sunset"]
    sunrise_local = get_local_time(sunrise_utc, timezone_offset)
    sunset_local = get_local_time(sunset_utc, timezone_offset)
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    now_local = now_utc + datetime.timedelta(seconds=timezone_offset)
    length = sunset_local - sunrise_local
    weather_main = weather["weather"][0]["main"]
    wd_ru, wd_en = code_ru_en.get(weather_main, ("Не понятно, какая погода", "Weather unclear"))
    if language == 'ru':
        weather_message += (
        f"{now_local.strftime('%Y-%m-%d %H:%M')} \n"
        f"Температура: {temp}°C {wd_ru}\n"
        f"Ощущается как: {temp1}°C \n"
        f"Влажность: {humidity}%\n"
        f"Давление: {math.ceil(pressure / 1.333)} мм.рт.ст\n"
        f"Ветер: {wind} м/с \n"
        f"Восход солнца: {sunrise_local.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Закат солнца: {sunset_local.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Продолжительность дня: {length}"
    )
    else:
        weather_message += (
        f"{now_local.strftime('%Y-%m-%d %H:%M')} \n"
        f"Temperature: {temp}°C {wd_en}\n"
        f"Feels like: {temp1}°C \n"
        f"Humidity: {humidity}%\n"
        f"Pressure: {math.ceil(pressure / 1.333)} mmHg\n"
        f"Wind: {wind} m/s \n"
        f"Sunrise: {sunrise_local.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Sunset: {sunset_local.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Length of day: {length}"
    )
    response = requests.get(f"http://api.openweathermap.org/data/2.5/forecast?q={city}&lang=ru&units=metric&appid=API")
    data = response.json()
# Получаем текущий день
    today = datetime.datetime.now().date()
    dates_of_interest = [today + datetime.timedelta(days=i) for i in range(3)]
# Время, которое нас интересует (часы)
    target_hours = [1, 7, 13, 19]
    time_periods = {
    1: 'Ночь',
    7: 'Утро',
    13: 'Полдень',
    19: 'Вечер'
    }
    forecast_message = f"Прогноз погоды в городе: {city}" if language == 'ru' else f"Weather forecast in the city: {city}"

    grouped_forecasts = {}

    for forecast in data['list']:
        date_time = datetime.datetime.fromtimestamp(forecast["dt"])
        forecast_date = date_time.date()
        if forecast_date in dates_of_interest and date_time.hour in target_hours:
            if forecast_date not in grouped_forecasts:
                grouped_forecasts[forecast_date] = []
            grouped_forecasts[forecast_date].append(forecast)

    # Теперь выводим по датам
    for date_key in sorted(grouped_forecasts.keys()):
        # Выводим дату
        if language == 'ru':
            forecast_message += f"\n{date_key.strftime('%Y-%m-%d')}\n"
        else:
            forecast_message += f"\n{date_key.strftime('%Y-%m-%d')}\n"

        # Для каждого прогноза в этот день, сортируем по времени
        for fc in sorted(grouped_forecasts[date_key], key=lambda x: x['dt']):
            dt_obj = datetime.datetime.fromtimestamp(fc["dt"])
            hour = dt_obj.hour
            # Определяем название периода времени
            period_name = time_periods.get(hour, dt_obj.strftime('%H:%M'))

            temp = fc["main"]["temp"]
            temp1 = fc["main"]["feels_like"]
            humidity = fc["main"]["humidity"]
            pressure = fc["main"]["pressure"]
            wind_speed = fc["wind"]["speed"]
            weather_main = fc["weather"][0]["main"]
            wd_ru, wd_en = code_ru_en.get(weather_main, ("Не понятно, какая погода", "Weather unclear"))

            if language == 'ru':
                forecast_message += (
                    f"{period_name}: Температура: {temp:.2f}°C {wd_ru}\n"
                    f"Ощущается как: {temp1:.2f}°C \n"
                )
            else:
                forecast_message += (
                    f"{period_name}: Temperature: {temp:.2f}°C {wd_en}\n"
                    f"Feels like: {temp1:.2f}°C \n"
                )
    button_1 = types.InlineKeyboardButton(text="Погода на 3 дня", callback_data="button_1")
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[button_1]])
    await message.reply(weather_message, reply_markup=keyboard)

@dp.callback_query(F.data == "button_1")
async def handle_button_click(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    language = user_languages.get(user_id, 'ru')
    await bot.send_message(user_id, forecast_message)
    await callback_query.answer()
async def main():
   await dp.start_polling(bot)
if __name__ == '__main__':
   asyncio.run(main())