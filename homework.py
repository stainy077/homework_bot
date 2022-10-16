from http import HTTPStatus
from urllib3.exceptions import HTTPError
import logging
import os
import requests
import time

from dotenv import load_dotenv

# from logging.handlers import RotatingFileHandler

from telegram import Bot

load_dotenv()

PRACTICUM_TOKEN = os.environ.get('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# RETRY_TIME = 5
# ERROR_RETRY = 5
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
# logger = logging.getLogger(__name__)
# handler = RotatingFileHandler('bot_log.log', maxBytes=50000000, backupCount=5)
# logger.addHandler(handler)


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
    headers = HEADERS
    params = {'from_date': timestamp}
    homework_statuses = None
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=headers,
            params=params,
        )
    except Exception as error:
        logging.error(f'Недоступность API-сервиса! {error}')
    if homework_statuses:
        status = homework_statuses.status_code
        if status != HTTPStatus.OK:
            raise HTTPError(f'Недоступность API-сервиса! HTTPStatus: {status}')
        logging.info('Получен ответ от API-сервиса')
        return homework_statuses.json()
    raise ValueError('список домашних работ не сформирован!')


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
    if 'homework_name' in homework:
        homework_name = homework.get('homework_name', '«Название домашней работы»')
    else:
        raise KeyError('Отсутствует название домашней работы в словаре!')
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
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная переменная окружения!!!')
        raise AttributeError('Не определён токен или номер чата!')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = '0000000000'
    # current_timestamp = int(time.time())
    logging.debug('Бот запущен')
    bot.send_message(TELEGRAM_CHAT_ID, 'Бот запущен')
    previos_hw_status = ''
    previos_error = ''

    while True:
        try:
            homework_statuses = get_api_answer(current_timestamp)
            homework = check_response(homework_statuses)
            message = parse_status(homework)
            if message != previos_hw_status:
                send_message(bot, message)
                previos_hw_status = message
            else:
                logging.debug('Отсутствие в ответе новых статусов!')
                raise Exception('Отсутствие в ответе новых статусов!')
            current_timestamp = homework_statuses.get('current_date', current_timestamp)
            time.sleep(RETRY_TIME)

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            if error_message != previos_error:
                bot.send_message(TELEGRAM_CHAT_ID, error_message)
                previos_error = error_message
            logging.error(error_message)
            time.sleep(ERROR_RETRY)


if __name__ == '__main__':
    main()
