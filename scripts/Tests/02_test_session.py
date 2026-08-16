#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тестирование сессий DeepSeek API через curl
Проверяет, что conversation_id работает и API помнит контекст
"""

import json
import subprocess
import sys
from typing import Optional, Tuple

# ============================================
# КОНФИГУРАЦИЯ
# ============================================

API_URL = "http://localhost:8001/v1/chat/completions"
DEFAULT_SESSION_ID = "test_session_123"

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
NC = '\033[0m'

def print_success(msg):
    print(f"{GREEN}✅ {msg}{NC}")

def print_error(msg):
    print(f"{RED}❌ {msg}{NC}")

def print_info(msg):
    print(f"{BLUE}ℹ️  {msg}{NC}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{NC}")

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

# ============================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С CURL
# ============================================

def send_request(messages: list, conversation_id: Optional[str] = None) -> dict:
    """
    Отправка запроса к DeepSeek API через curl
    
    Args:
        messages: Список сообщений [{"role": "user", "content": "..."}]
        conversation_id: ID беседы для продолжения диалога
        
    Returns:
        Ответ от API в виде dict
    """
    # Формируем payload
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    # Преобразуем в JSON
    payload_json = json.dumps(payload)
    
    # Формируем curl команду
    curl_cmd = [
        "curl",
        "-s",  # тихий режим
        "-X", "POST",
        API_URL,
        "-H", "Content-Type: application/json",
        "-d", payload_json
    ]
    
    # Выполняем
    try:
        result = subprocess.run(
            curl_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print_error(f"Ошибка curl: {result.stderr}")
            return None
        
        # Парсим ответ
        try:
            response = json.loads(result.stdout)
            return response
        except json.JSONDecodeError as e:
            print_error(f"Ошибка парсинга JSON: {e}")
            print(f"Ответ: {result.stdout[:200]}...")
            return None
            
    except subprocess.TimeoutExpired:
        print_error("Таймаут запроса")
        return None
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return None

def extract_conversation_id(response: dict) -> Optional[str]:
    """Извлечение conversation_id из ответа"""
    if response and 'conversation_id' in response:
        return response['conversation_id']
    return None

def extract_answer(response: dict) -> Optional[str]:
    """Извлечение ответа ассистента"""
    if response and 'choices' in response and response['choices']:
        return response['choices'][0]['message']['content']
    return None

# ============================================
# ТЕСТЫ
# ============================================

def test_simple_request():
    """Тест 1: Простой запрос без сессии"""
    print_header("ТЕСТ 1: ПРОСТОЙ ЗАПРОС")
    
    messages = [
        {"role": "user", "content": "Привет! Как дела?"}
    ]
    
    response = send_request(messages)
    
    if not response:
        print_error("Не удалось получить ответ")
        return False
    
    answer = extract_answer(response)
    conv_id = extract_conversation_id(response)
    
    print_info(f"Ответ: {answer[:100]}...")
    print_info(f"Conversation ID: {conv_id}")
    
    if conv_id:
        print_success("Получен conversation_id")
        return True
    else:
        print_error("Не получен conversation_id")
        return False

def test_session_creation():
    """Тест 2: Создание сессии с именем"""
    print_header("ТЕСТ 2: СОЗДАНИЕ СЕССИИ")
    
    messages = [
        {"role": "user", "content": "Меня зовут Алексей. Я люблю программирование на Python."}
    ]
    
    response = send_request(messages)
    conv_id = extract_conversation_id(response)
    answer = extract_answer(response)
    
    if not conv_id:
        print_error("Не удалось создать сессию")
        return None
    
    print_info(f"Создан conversation_id: {conv_id}")
    print_info(f"Ответ: {answer[:100]}...")
    print_success("Сессия создана")
    
    return conv_id

def test_session_continue(conv_id: str):
    """Тест 3: Продолжение сессии"""
    print_header("ТЕСТ 3: ПРОДОЛЖЕНИЕ СЕССИИ")
    
    messages = [
        {"role": "user", "content": "Какое мое любимое хобби?"}
    ]
    
    response = send_request(messages, conversation_id=conv_id)
    
    if not response:
        print_error("Не удалось получить ответ")
        return False
    
    new_conv_id = extract_conversation_id(response)
    answer = extract_answer(response)
    
    print_info(f"Старый conversation_id: {conv_id}")
    print_info(f"Новый conversation_id: {new_conv_id}")
    print_info(f"Ответ: {answer[:150]}...")
    
    # Проверяем, помнит ли API
    if "программирование" in answer.lower() or "python" in answer.lower():
        print_success("✅ API ПОМНИТ контекст! (упомянул программирование)")
        return True
    else:
        print_warning("⚠️ API не упомянул программирование")
        print_info("Проверьте, что ответ учитывает предыдущий контекст")
        return False

def test_session_check_memory(conv_id: str):
    """Тест 4: Проверка памяти (имя)"""
    print_header("ТЕСТ 4: ПРОВЕРКА ПАМЯТИ")
    
    messages = [
        {"role": "user", "content": "Как меня зовут?"}
    ]
    
    response = send_request(messages, conversation_id=conv_id)
    
    if not response:
        print_error("Не удалось получить ответ")
        return False
    
    new_conv_id = extract_conversation_id(response)
    answer = extract_answer(response)
    
    print_info(f"Conversation ID: {new_conv_id}")
    print_info(f"Ответ: {answer[:150]}...")
    
    # Проверяем, помнит ли имя
    if "алексей" in answer.lower() or "alexey" in answer.lower():
        print_success("✅ API ПОМНИТ ИМЯ! (Алексей)")
        return True
    else:
        print_warning("⚠️ API не назвал имя")
        print_info("Проверьте, что API помнит имя из первого запроса")
        return False

def test_new_session():
    """Тест 5: Новая сессия (без conversation_id)"""
    print_header("ТЕСТ 5: НОВАЯ СЕССИЯ")
    
    messages = [
        {"role": "user", "content": "Меня зовут Мария. Я люблю рисование."}
    ]
    
    response = send_request(messages)
    conv_id = extract_conversation_id(response)
    answer = extract_answer(response)
    
    if not conv_id:
        print_error("Не удалось создать сессию")
        return False
    
    print_info(f"Новый conversation_id: {conv_id}")
    print_info(f"Ответ: {answer[:100]}...")
    print_success("Новая сессия создана")
    
    return conv_id

def test_cross_session(conv_id1: str, conv_id2: str):
    """Тест 6: Проверка, что сессии не пересекаются"""
    print_header("ТЕСТ 6: РАЗНЫЕ СЕССИИ")
    
    # Проверяем первую сессию
    messages1 = [{"role": "user", "content": "Какое мое хобби?"}]
    response1 = send_request(messages1, conversation_id=conv_id1)
    answer1 = extract_answer(response1)
    
    # Проверяем вторую сессию
    messages2 = [{"role": "user", "content": "Какое мое хобби?"}]
    response2 = send_request(messages2, conversation_id=conv_id2)
    answer2 = extract_answer(response2)
    
    # Проверяем, что ответы разные
    if answer1 and answer2:
        print_info(f"Сессия 1 ({conv_id1[:8]}...): {answer1[:80]}...")
        print_info(f"Сессия 2 ({conv_id2[:8]}...): {answer2[:80]}...")
        
        # Проверяем, что ответы соответствуют разным сессиям
        if "программирование" in answer1.lower() and "рисование" in answer2.lower():
            print_success("✅ Сессии работают независимо!")
            return True
        else:
            print_warning("⚠️ Не удалось однозначно проверить независимость сессий")
            return False
    else:
        print_error("Не удалось получить ответы")
        return False

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

def main():
    """Запуск всех тестов"""
    print_header("🧪 ТЕСТИРОВАНИЕ СЕССИЙ DEEPSEEK API")
    
    # Проверяем, что сервер запущен
    print_info("Проверка сервера...")
    test_response = send_request([{"role": "user", "content": "ping"}])
    if not test_response:
        print_error("Сервер не отвечает!")
        print_info("Запустите сервер: ./scripts/04_run_server_only.sh start")
        return False
    
    print_success("Сервер работает")
    
    # Запускаем тесты
    results = []
    
    # Тест 1: Простой запрос
    results.append(("Простой запрос", test_simple_request()))
    
    # Тест 2: Создание сессии
    conv_id = test_session_creation()
    if conv_id:
        results.append(("Создание сессии", True))
        
        # Тест 3: Продолжение сессии
        results.append(("Продолжение сессии", test_session_continue(conv_id)))
        
        # Тест 4: Проверка памяти
        results.append(("Проверка памяти", test_session_check_memory(conv_id)))
    else:
        results.append(("Создание сессии", False))
    
    # Тест 5: Новая сессия
    conv_id2 = test_new_session()
    if conv_id2:
        results.append(("Новая сессия", True))
        
        # Тест 6: Разные сессии
        if conv_id:
            results.append(("Независимость сессий", test_cross_session(conv_id, conv_id2)))
    else:
        results.append(("Новая сессия", False))
    
    # Итоги
    print_header("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    
    passed = 0
    failed = 0
    for name, result in results:
        if result:
            print_success(f"{name}: ПРОЙДЕН")
            passed += 1
        else:
            print_error(f"{name}: НЕ ПРОЙДЕН")
            failed += 1
    
    print("\n" + "="*60)
    print(f"  Всего тестов: {len(results)}")
    print(f"  {GREEN}Пройдено: {passed}{NC}")
    print(f"  {RED}Не пройдено: {failed}{NC}")
    print("="*60)
    
    if failed == 0:
        print_success("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Сессии работают корректно.")
        return True
    else:
        print_warning("⚠️ Некоторые тесты не пройдены. Проверьте логи.")
        return False

# ============================================
# ЗАПУСК
# ============================================

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)