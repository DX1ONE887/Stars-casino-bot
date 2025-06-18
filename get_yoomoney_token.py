import requests
import webbrowser
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

def get_yoomoney_token():
    # Получаем данные из .env
    CLIENT_ID = os.getenv('YOOMONEY_CLIENT_ID')
    CLIENT_SECRET = os.getenv('YOOMONEY_CLIENT_SECRET')
    REDIRECT_URI = os.getenv('YOOMONEY_REDIRECT_URI', 'https://example.com')
    
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Ошибка: Не заданы YOOMONEY_CLIENT_ID или YOOMONEY_CLIENT_SECRET в .env файле")
        return
    
    # Шаг 1: Получение кода авторизации
    auth_url = (
        f"https://yoomoney.ru/oauth/authorize?"
        f"client_id={CLIENT_ID}&"
        f"response_type=code&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=operation-history%20operation-details"
    )
    
    print("Открываю браузер для авторизации...")
    webbrowser.open(auth_url)
    
    # Шаг 2: Получение кода от пользователя
    code = input("После авторизации скопируйте код из URL и введите здесь: ").strip()
    
    # Шаг 3: Обмен кода на токен
    token_url = "https://yoomoney.ru/oauth/token"
    payload = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }
    
    response = requests.post(token_url, data=payload)
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        print("\n" + "="*50)
        print("Успешно получен токен доступа!")
        print("Добавьте его в ваш .env файл:")
        print(f"YOOMONEY_TOKEN={access_token}")
        print("="*50)
        
        # Сохраняем токен в .env
        with open('.env', 'a') as env_file:
            env_file.write(f"\nYOOMONEY_TOKEN={access_token}\n")
        
        print("Токен автоматически добавлен в .env файл")
    else:
        print(f"Ошибка: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    get_yoomoney_token()