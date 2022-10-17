import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot
from urllib3.exceptions import HTTPError

load_dotenv()

PRACTICUM_TOKEN = os.environ.get('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ERROR_RETRY = 30
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(name)s, %(message)s',
    filename='bot_log.log',
    filemode='a',
)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.info('Сообщение о статусе домашки отправлено в Telegram-чат')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Сообщение не отправлено в Telegram-чат : {error}')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса. Возвращает ответ API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = None
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except Exception as error:
        logging.error(f'Недоступность API-сервиса! {error}')
        raise HTTPError(f'Недоступность API-сервиса! {error}')
    status = homework_statuses.status_code
    if status != HTTPStatus.OK:
        raise HTTPError(f'Недоступность API-сервиса! HTTPStatus: {status}')
    logging.info('Получен ответ от API-сервиса')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Входные данные не являются словарём!')
    homeworks = response.get('homeworks')
    if not homeworks:
        logging.error('Отсутствуют данные о домашних работах!')
        raise KeyError('Отсутствуют данные о домашних работах!')
    if not isinstance(homeworks, list):
        raise TypeError('Данные о домашних работах представлены некорректно!')
    return homeworks[0]


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе её статус."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует название домашней работы в словаре!')
    homework_name = homework.get('homework_name', '«Название домашней работы»')
    homework_status = homework.get('status', 'empty_status')
    if homework_status not in HOMEWORK_STATUSES:
        status_text = f'Неизвестный статус: {homework_status}'
        logging.error(status_text)
        return status_text
    else:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    return False


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная переменная окружения!!!')
        raise AttributeError('Не определён токен или номер чата!')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    logging.debug('Бот запущен')
    bot.send_message(TELEGRAM_CHAT_ID, 'Бот запущен')
    previos_message = ''
    message = ''
    sleep_time = RETRY_TIME

    while True:
        try:
            homework_statuses = get_api_answer(current_timestamp)
            homework = check_response(homework_statuses)
            message = parse_status(homework)
            current_timestamp = homework_statuses.get(
                'current_date',
                current_timestamp,
            )
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            sleep_time = ERROR_RETRY
        finally:
            if message != previos_message:
                send_message(bot, message)
                previos_message = message
                logging.debug(f'Текст статуса/ошибки: {message}')
            else:
                logging.debug('Отсутствие в ответе новых статусов!')
                raise Exception('Отсутствие в ответе новых статусов!')
            time.sleep(sleep_time)


if __name__ == '__main__':
    main()
