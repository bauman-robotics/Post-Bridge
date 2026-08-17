#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Главный скрипт-оркестратор
Загружает конфиг и секреты из отдельных файлов
"""

import os
import sys
import yaml
import signal
import time
import json
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple

# ================================
# ОПРЕДЕЛЯЕМ КОРЕНЬ ПРОЕКТА
# ================================
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
# ================================

# Импортируем модули
from deepseek_client import DeepSeekClient
from email_reader import EmailReader
from email_sender import EmailSender
from logger import get_logger

class EmailBridge:
    """Основной класс-оркестратор"""
    
    def __init__(self, config_path: str = "config/config.yaml", secrets_path: str = "config/secrets.yaml"):
        """Инициализация с загрузкой конфига и секретов"""
        self.config = self.load_config(config_path, secrets_path)
        self.running = True
        
        # Инициализируем логгер
        self.logger = get_logger()
        
        # Загружаем сохраненные сессии
        self.sessions_file = Path("data/sessions.json")
        self.sessions_file.parent.mkdir(exist_ok=True, parents=True)
        self.sessions = self.load_sessions()
        
        # Выводим конфигурацию при старте
        self.print_config()
        
        # Инициализируем компоненты
        self.deepseek = DeepSeekClient(self.config.get('deepseek', {}))
        self.email_reader = EmailReader(self.config.get('email', {}))
        self.email_sender = EmailSender(self.config.get('email', {}))
        
        # Настройка обработки сигналов
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Статистика
        self.stats = {
            'processed': 0,
            'errors': 0,
            'sessions_continued': 0,
            'sessions_started': 0,
            'started': datetime.now().isoformat()
        }
    
    def _run_polling_mode(self):
        """Режим пуллинга (проверка каждые N секунд)"""
        interval = self.config.get('general', {}).get('email_check_interval', 60)
        
        self.logger.info(f"📡 Режим polling: проверка каждые {interval} сек")
        print(f"📡 Режим polling: проверка каждые {interval} сек")
        
        consecutive_errors = 0
        
        while self.running:
            try:
                # ===== ПРОВЕРКА СОЕДИНЕНИЯ ПЕРЕД ЗАПУСКОМ =====
                if self.email_reader and not self.email_reader.is_connected():
                    self.logger.warning("⚠️ IMAP соединение разорвано, переподключаюсь...")
                    self.email_reader.disconnect()
                    if not self.email_reader.connect():
                        self.logger.error("❌ Не удалось переподключиться к IMAP")
                        time.sleep(10)
                        continue
                
                # Добавляем таймаут
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Operation timed out")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
                # Проверяем почту
                self.run_email_processing()
                
                signal.alarm(0)
                
                # Сброс счетчика ошибок
                consecutive_errors = 0
                
                # Ожидание
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)
                        
            except TimeoutError:
                consecutive_errors += 1
                self.logger.error(f"⏰ Таймаут операции (ошибка #{consecutive_errors})")
                self.email_reader.disconnect()
                time.sleep(min(consecutive_errors * 5, 30))
                    
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"❌ Ошибка #{consecutive_errors}: {e}")
                self.email_reader.disconnect()
                if not self.running:
                    break
                time.sleep(min(consecutive_errors * 5, 30))

    def _run_idle_mode(self):
        """Режим IDLE (мгновенная реакция)"""
        idle_timeout = self.config.get('general', {}).get('idle_timeout', 60)
        
        self.logger.info(f"📡 Режим idle: ожидание до {idle_timeout} сек")
        print(f"📡 Режим idle: ожидание до {idle_timeout} сек")
        
        while self.running:
            try:
                # Подключаемся
                if not self.email_reader.connect():
                    time.sleep(10)
                    continue
                
                # Ждем новые письма
                if self.email_reader.wait_for_new_emails(timeout=idle_timeout):
                    self.run_email_processing()
                
                # Отключаемся (переподключение в следующей итерации)
                self.email_reader.disconnect()
                
            except Exception as e:
                self.logger.error(f"❌ Ошибка в idle цикле: {e}")
                print(f"❌ Ошибка в idle цикле: {e}")
                self.email_reader.disconnect()
                time.sleep(10)

    def _run_hybrid_mode(self):
        """Гибридный режим: IDLE + резервный пуллинг"""
        # ОТЛАДКА: проверяем состояние при входе
        print(f"\n🔍 Вход в hybrid_mode: self.running = {self.running}")
        self.logger.info(f"🔍 Вход в hybrid_mode: self.running = {self.running}")
        
        if not self.running:
            print("❌ self.running = False при входе в гибридный режим!")
            import traceback
            traceback.print_stack()
            return
        
        idle_timeout = self.config.get('general', {}).get('idle_timeout', 60)
        
        fallback_interval = self.config.get('general', {}).get('fallback_poll_interval', 600)
        
        self.logger.info(f"📡 Режим hybrid: IDLE {idle_timeout}сек + резервный пуллинг {fallback_interval}сек")
        print(f"📡 Режим hybrid: IDLE {idle_timeout}сек + резервный пуллинг {fallback_interval}сек")
        
        last_poll = 0
        
        while self.running:
            try:
                # ===== ПРОВЕРКА В НАЧАЛЕ ЦИКЛА =====
                if not self.running:
                    self.logger.info("🛑 Выход: флаг сброшен в начале цикла")
                    break
                
                # Подключаемся
                if not self.email_reader.connect():
                    if not self.running:
                        break
                    time.sleep(10)
                    continue
                
                # ===== ОТЛАДКА ПРЯМО ЗДЕСЬ =====
                print(f"🔍 ПОСЛЕ connect: self.running = {self.running}")
                self.logger.info(f"🔍 ПОСЛЕ connect: self.running = {self.running}")

                
                # ===== ПРОВЕРКА ПОСЛЕ ПОДКЛЮЧЕНИЯ =====
                if not self.running:
                    self.email_reader.disconnect()
                    self.logger.info("🛑 Выход: флаг сброшен после подключения")
                    break
                
                # Ждем новые письма
                new_emails = self.email_reader.wait_for_new_emails(
                    timeout=idle_timeout,
                    stop_check=lambda: not self.running
                )
                
                # ===== ПРОВЕРКА ПОСЛЕ ОЖИДАНИЯ =====
                if not self.running:
                    self.email_reader.disconnect()
                    self.logger.info("🛑 Выход: флаг сброшен после IDLE")
                    break
                
                # Если IDLE сработал или прошло время резервной проверки
                current_time = time.time()
                if new_emails or (current_time - last_poll > fallback_interval):
                    self.run_email_processing()
                    last_poll = current_time
                
                # ===== ПРОВЕРКА ПОСЛЕ ОБРАБОТКИ =====
                if not self.running:
                    self.email_reader.disconnect()
                    self.logger.info("🛑 Выход: флаг сброшен после обработки")
                    break
                
                # Отключаемся
                self.email_reader.disconnect()
                
            except Exception as e:
                self.logger.error(f"❌ Ошибка в гибридном цикле: {e}")
                print(f"❌ Ошибка в гибридном цикле: {e}")
                try:
                    self.email_reader.disconnect()
                except:
                    pass
                if not self.running:
                    self.logger.info("🛑 Выход: флаг сброшен после ошибки")
                    break
                time.sleep(10)
        
        self.logger.info("👋 Завершение гибридного режима")
        print("👋 Завершение гибридного режима")

    def signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        import os
        
        # Игнорируем сигналы, если они пришли не от терминала
        # Сигналы от системы обычно приходят с PID = 0 или 1
        if frame and frame.f_code.co_filename == '<signal handler>':
            print(f"\n🛑 Системный сигнал {signum} - игнорирую")
            return
        
        print(f"\n🛑 Получен сигнал {signum}. Останавливаюсь...")
        
        # Устанавливаем флаг остановки
        self.running = False
        self.logger.info(f"🛑 Получен сигнал {signum}")  # <-- ДОБАВИТЬ
        self.logger.info("🛑 Получен сигнал завершения")
        
        # Отключаемся от почты
        if hasattr(self, 'email_reader') and self.email_reader:
            try:
                if self.email_reader.imap:
                    self.email_reader.imap.send(b'DONE\r\n')
                    self.logger.debug("✅ Отправлен DONE в IDLE")
            except:
                pass
            
            try:
                self.email_reader.disconnect()
            except:
                pass
        
        # ===== НЕ ЖДЕМ 2 СЕКУНДЫ, ВЫХОДИМ СРАЗУ =====
        # Это гарантирует завершение, даже если цикл завис
        import threading
        def force_exit():
            time.sleep(1)  # Даем время на корректное завершение
            self.logger.warning("⚠️ Принудительный выход")
            os._exit(0)
        
        exit_thread = threading.Thread(target=force_exit)
        exit_thread.daemon = True
        exit_thread.start()
    
    def load_config(self, config_path: str, secrets_path: str) -> Dict:
        """Загрузка конфигурации и секретов"""
        default_config = {
            'general': {},
            'deepseek': {},
            'email': {},
            'batch': {},
            'processing': {},
            'logging': {},
            'filters': {}
        }
        
        config = default_config.copy()
        
        # Загружаем основной конфиг
        if Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        for key in default_config:
                            if key in user_config:
                                config[key] = user_config[key]
                print(f"✅ Конфиг загружен: {config_path}")
            except Exception as e:
                print(f"⚠️  Ошибка загрузки конфига: {e}")
        else:
            print(f"⚠️  Конфиг не найден: {config_path}")
        
        # Загружаем секреты
        if Path(secrets_path).exists():
            try:
                with open(secrets_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        print("⚠️  secrets.yaml пуст")
                        return config
                    secrets = yaml.safe_load(content)
                    
                    # ===== ПЕРЕНЕСЕМ ВСЕ СЕКРЕТЫ В КОНФИГ =====
                    # Email настройки из секретов
                    if secrets and 'email' in secrets:
                        email_secrets = secrets['email']
                        
                        # Создаем секцию email если её нет
                        if 'email' not in config:
                            config['email'] = {}
                        
                        # Переносим все поля из secrets в config
                        for key, value in email_secrets.items():
                            config['email'][key] = value
                            print(f"   🔐 {key}: загружен из секретов")
                    
                    print("🔐 Секреты загружены")
                    
            except yaml.YAMLError as e:
                print(f"⚠️  Ошибка парсинга secrets.yaml: {e}")
                print("   Проверьте правильность YAML формата")
            except Exception as e:
                print(f"⚠️  Ошибка загрузки секретов: {e}")
        else:
            print(f"⚠️  Файл секретов не найден: {secrets_path}")
            print("   Создайте config/secrets.yaml:")
            print("   email:")
            print("     username: 'bridge.post@ya.ru'")
            print("     password: 'your_app_password'")
            print("     imap_server: 'imap.yandex.ru'")
            print("     smtp_server: 'smtp.yandex.ru'")
            print("     smtp_port: 465")
        
        return config
    
    def load_sessions(self) -> Dict:
        """Загрузка сохраненных сессий"""
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем старый формат (строка) в новый (список)
                    for email, value in data.items():
                        if isinstance(value, str):
                            data[email] = [value]
                    return data
            except:
                return {}
        return {}
        
    def save_sessions(self):
        """Сохранение сессий в файл"""
        try:
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения сессий: {e}")
    
    def get_session_id_for_sender(self, from_addr: str) -> Optional[str]:
        """Получение последней сессии для отправителя"""
        if from_addr in self.sessions and self.sessions[from_addr]:
            # Возвращаем ПОСЛЕДНЮЮ сессию из списка
            return self.sessions[from_addr][-1]
        return None
        
    def session_exists(self, session_id: str) -> bool:
        """Проверка, существует ли сессия с таким ID"""
        for email, sessions in self.sessions.items():
            if session_id in sessions:
                return True
        return False

    def extract_session_id_from_subject(self, subject: str) -> Optional[str]:
        """Извлечение session_id из темы письма"""
        if not subject:
            return None
        # Разрешаем двоеточие в SID (формат: UUID:номер)
        match = re.search(r'\[SID:([a-zA-Z0-9\-_:]+)\]', subject)
        if match:
            return match.group(1)
        return None

    def generate_session_id(self) -> str:
        """Генерация нового session_id"""
        # Вместо короткого UUID генерируем полный
        import uuid
        return str(uuid.uuid4())  # Полный UUID
        
    def print_config(self):
        """Вывод конфигурации в консоль и лог"""
        print("\n" + "="*70)
        print("🚀 ЗАПУСК ПОЧТОВОГО МОСТА")
        print("="*70)
        
        general = self.config.get('general', {})
        print("\n⚙️  ОБЩИЕ НАСТРОЙКИ:")
        print(f"   Режим: {general.get('mode', 'server')}")
        print(f"   Обработка почты: {'✅ Включена' if general.get('enable_email_processing', True) else '❌ Отключена'}")
        print(f"   Пакетная обработка: {'✅ Включена' if general.get('enable_batch_processing', False) else '❌ Отключена'}")
        print(f"   Интервал проверки: {general.get('email_check_interval', 60)} сек")
        print(f"   Максимум писем за раз: {general.get('max_emails_per_check', 5)}")
        print(f"   Сессии: {'✅ Включены' if general.get('enable_sessions', True) else '❌ Отключены'}")
        if general.get('enable_sessions', True):
            print(f"   Сохранено сессий: {len(self.sessions)}")
        
        deepseek = self.config.get('deepseek', {})
        print("\n🤖 DEEPSEEK API:")
        print(f"   URL: {deepseek.get('api_url', 'http://localhost:8000')}")
        print(f"   Модель: {deepseek.get('model', 'deepseek-chat')}")
        
        email = self.config.get('email', {})
        print("\n📧 EMAIL:")
        print(f"   Аккаунт: {email.get('username', 'Не указан')}")
        print(f"   IMAP сервер: {email.get('imap_server', 'Не указан')}")
        print(f"   SMTP сервер: {email.get('smtp_server', 'Не указан')}")
        print(f"   Пароль: {'✅ Установлен' if email.get('password') else '❌ Не установлен'}")
        
        batch = self.config.get('batch', {})
        print("\n📁 ПАКЕТНАЯ ОБРАБОТКА:")
        print(f"   Входная папка: {batch.get('input_dir', 'requests')}")
        print(f"   Выходная папка: {batch.get('output_dir', 'responses')}")
        
        filters = self.config.get('filters', {})
        print("\n🔍 ФИЛЬТРЫ:")
        subject_contains = filters.get('subject_contains', [])
        if subject_contains:
            print(f"   ✅ Обязательные слова в теме: {subject_contains}")
        else:
            print(f"   ❌ Обязательные слова в теме: НЕ УСТАНОВЛЕНЫ (все письма проходят)")
        
        print("\n" + "="*70)
        print("✅ Почтовый мост запущен!")
        print("="*70 + "\n")
        
        # Записываем в лог
        self.logger.info("="*70)
        self.logger.info("🚀 ЗАПУСК ПОЧТОВОГО МОСТА")
        self.logger.info("="*70)
        self.logger.info(f"🤖 DeepSeek API: {deepseek.get('api_url', 'http://localhost:8000')}")
        self.logger.info(f"📧 Email: {email.get('username', 'Не указан')}")
        self.logger.info(f"💾 Сохранено сессий: {len(self.sessions)}")
        self.logger.info("="*70)
    
    def process_question_with_session(self, 
                                     question: str,
                                     from_addr: str = "batch@local",
                                     subject: str = "",
                                     session_id: Optional[str] = None) -> tuple[Optional[str], Optional[str], bool]:
        """
        Обработка вопроса с управлением сессией
        
        Args:
            question: Текст вопроса
            from_addr: Идентификатор отправителя (email или имя файла)
            subject: Тема (для извлечения session_id)
            session_id: Переданный session_id (для batch режима)
            
        Returns:
            (ответ, session_id, is_new_session)
        """
        enable_sessions = self.config.get('general', {}).get('enable_sessions', True)
        is_new_session = False
        used_session_id = None
        
        if enable_sessions:
            # 1. Если передан session_id (для batch режима)
            if session_id:
                # Проверяем, существует ли сессия в списках
                found = False
                for email, sessions in self.sessions.items():
                    if session_id in sessions:
                        found = True
                        # Находим владельца
                        if email == from_addr:
                            used_session_id = session_id
                            self.logger.info(f"🔄 Продолжение сессии {session_id} для {from_addr} (из batch)")
                            print(f"🔄 Продолжение сессии: {session_id}")
                            self.stats['sessions_continued'] += 1
                        else:
                            self.logger.warning(f"⚠️ Session {session_id} принадлежит {email}, а запрос от {from_addr}. Начинаем новую сессию.")
                            is_new_session = True
                        break
                if not found:
                    self.logger.warning(f"⚠️ Session ID {session_id} не найден. Начинаем новую сессию.")
                    is_new_session = True

            # 2. Если нет session_id, пробуем извлечь из subject
            if not used_session_id and not is_new_session:
                extracted_sid = self.extract_session_id_from_subject(subject)
                if extracted_sid:
                    # Проверяем, существует ли сессия
                    if self.session_exists(extracted_sid):
                        # Находим владельца
                        for email, sessions in self.sessions.items():
                            if extracted_sid in sessions:
                                if email == from_addr:
                                    used_session_id = extracted_sid
                                    self.logger.info(f"🔄 Продолжение сессии {extracted_sid} для {from_addr} (из темы)")
                                    print(f"🔄 Продолжение сессии: {extracted_sid}")
                                    self.stats['sessions_continued'] += 1
                                else:
                                    self.logger.warning(f"⚠️ Session {extracted_sid} принадлежит {email}")
                                    is_new_session = True
                                break
                    else:
                        self.logger.warning(f"⚠️ Session ID {extracted_sid} не найден")
                        is_new_session = True
            
            # 3. Если нет session_id в теме - создаем новую сессию
            if not used_session_id and not is_new_session:
                # НЕ проверяем сохраненную сессию для отправителя
                # Всегда создаем новую, если в теме нет [SID:...]
                is_new_session = True
                # used_session_id остается None, API сам создаст conversation_id
                self.logger.info(f"✨ Создание новой сессии для {from_addr} (нет SID в теме)")
                print(f"✨ Создание новой сессии для {from_addr} (нет SID в теме)")
                self.stats['sessions_started'] += 1
            
            # Если все еще нет сессии - создаем новую
            if not used_session_id and is_new_session:
                # Не генерируем ID! API сам вернет conversation_id
                # used_session_id остается None, первый запрос будет без conversation_id
                self.logger.info(f"✨ Создание новой сессии для {from_addr}")
                print(f"✨ Создание новой сессии для {from_addr}")
                self.stats['sessions_started'] += 1
        
        # Получаем ответ от DeepSeek
        system_prompt = self.config.get('deepseek', {}).get('system_prompt')
        answer, new_session_id = self.deepseek.ask(
            question,
            system_prompt=system_prompt,
            conversation_id=used_session_id if enable_sessions else None  # <-- conversation_id вместо session_id
        )
        
        if answer and enable_sessions:
            if new_session_id:
                used_session_id = new_session_id
                # Сохраняем ВСЕ сессии (список)
                if from_addr not in self.sessions:
                    self.sessions[from_addr] = []
                # Добавляем новую сессию, если её ещё нет
                if used_session_id not in self.sessions[from_addr]:
                    self.sessions[from_addr].append(used_session_id)
                # Ограничиваем количество сессий (например, 20 последних)
                if len(self.sessions[from_addr]) > 20:
                    self.sessions[from_addr] = self.sessions[from_addr][-20:]
                self.save_sessions()
                self.logger.info(f"💾 Сессия {used_session_id} сохранена для {from_addr}")
                print(f"💾 Сессия сохранена: {used_session_id}")
        
        return answer, used_session_id, is_new_session
    
    def ask(self, 
            question: str, 
            system_prompt: Optional[str] = None,
            conversation_id: Optional[str] = None,
            **kwargs) -> Tuple[Optional[str], Optional[str]]:
        """
        Упрощенный метод для одного вопроса
        
        Args:
            question: Текст вопроса
            system_prompt: Системный промпт
            conversation_id: ID беседы для продолжения диалога
            **kwargs: Дополнительные параметры
            
        Returns:
            (Текст ответа, Conversation ID) или (None, None)
        """
        messages = []
        
        if system_prompt or self.config.get('system_prompt'):
            messages.append({
                "role": "system",
                "content": system_prompt or self.config.get('system_prompt')
            })
        
        messages.append({"role": "user", "content": question})
        
        response = self.chat(messages, conversation_id=conversation_id, **kwargs)
        
        if response and 'choices' in response and response['choices']:
            answer = response['choices'][0]['message']['content']
            new_conversation_id = response.get('conversation_id')
            
            # ===== ВЫВОД ТОКЕНОВ =====
            if 'usage' in response:
                usage = response['usage']
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', 0)
                
                # Сохраняем для передачи в email_sender
                self.last_usage = {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens
                }
                
                print(f"📊 Токены: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                # Логируем в файл
                if hasattr(self, 'logger'):
                    self.logger.info(f"📊 Токены: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
            else:
                self.last_usage = None
            
            return answer, new_conversation_id
        
        return None, None


    def send_response(self, 
                    to_email: str, 
                    question: str,
                    answer: str,
                    original_subject: str = "",
                    reply_to: Optional[str] = None,
                    include_question: Optional[bool] = None,
                    signature: Optional[str] = None,
                    session_id: Optional[str] = None,
                    is_new_session: bool = False,
                    token_stats: Optional[Dict] = None) -> bool:  # <-- ДОБАВЛЕНО
        """
        Отправка ответа на письмо
        
        Args:
            to_email: Email получателя
            question: Оригинальный вопрос
            answer: Ответ от DeepSeek
            original_subject: Оригинальная тема письма
            reply_to: Email для ответа
            include_question: Включать ли вопрос в тело письма (если None - берется из конфига)
            signature: Подпись в конце письма (если None - берется из конфига)
            session_id: ID сессии для включения в тему
            is_new_session: Флаг новой сессии
            token_stats: Статистика токенов (prompt_tokens, completion_tokens, total_tokens)
            
        Returns:
            True если отправлено успешно
        """
        if not self.smtp and not self.connect():
            return False
        
        try:
            # Создаем письмо
            msg = EmailMessage()
            
            # Тема с session_id
            if self.include_session_in_subject and session_id:
                session_tag = f"[SID:{session_id}]"
                
                if original_subject:
                    # Если тема уже содержит SID, заменяем его
                    if re.search(r'\[SID:[a-zA-Z0-9\-_]+\]', original_subject):
                        subject = re.sub(r'\[SID:[a-zA-Z0-9\-_]+\]', session_tag, original_subject)
                    else:
                        if not original_subject.lower().startswith('re:'):
                            subject = f"Re: {session_tag} {original_subject}"
                        else:
                            subject = f"{session_tag} {original_subject}"
                else:
                    subject = f"{session_tag} Ответ на ваш запрос"
            else:
                if original_subject:
                    if not original_subject.lower().startswith('re:'):
                        subject = f"Re: {original_subject}"
                    else:
                        subject = original_subject
                else:
                    subject = "Ответ на ваш запрос"
            
            msg['Subject'] = subject
            msg['From'] = self.config['username']
            msg['To'] = to_email
            
            # Добавляем In-Reply-To если есть
            if reply_to:
                msg['In-Reply-To'] = reply_to
            
            # Определяем параметры из конфига если не переданы явно
            if include_question is None:
                include_question = self.include_question
            if signature is None:
                signature = self.signature
            
            # Формируем тело письма
            body_parts = []
            
            # Приветствие
            greeting = self.config.get('greeting', "Здравствуйте!")
            body_parts.append(greeting)
            body_parts.append("")
            
            # Информация о сессии
            if session_id:
                if is_new_session:
                    body_parts.append(f"🆕 Начата новая сессия: **{session_id}**")
                else:
                    body_parts.append(f"🔄 Продолжение сессии: **{session_id}**")
                body_parts.append("")
            
            # Добавляем вопрос если нужно
            if include_question:
                body_parts.append("📝 **Ваш вопрос:**")
                body_parts.append(question)
                body_parts.append("")
            
            # Ответ
            body_parts.append("💬 **Ответ:**")
            body_parts.append(answer)
            body_parts.append("")
            
            # ===== СТАТИСТИКА ТОКЕНОВ =====
            if token_stats:
                total = token_stats.get('total_tokens', 0)
                prompt = token_stats.get('prompt_tokens', 0)
                completion = token_stats.get('completion_tokens', 0)
                body_parts.append("---")
                body_parts.append(f"📊 Токены: {total} (prompt: {prompt}, completion: {completion})")
                body_parts.append("")
            
            # Подпись
            body_parts.append("---")
            if signature:
                body_parts.append(signature)
            
            # Дополнительный футер
            if self.footer:
                body_parts.append(self.footer)
            
            # Дата
            current_date = datetime.now().strftime('%d.%m.%Y %H:%M')
            body_parts.append(f"📅 {current_date}")
            
            # Склеиваем всё в одно письмо
            body = '\n'.join(body_parts)
            
            msg.set_content(body, charset='utf-8')
            
            # Отправляем
            self.smtp.send_message(msg)
            print(f"✅ Ответ отправлен на {to_email}")
            print(f"   📝 Вопрос: {question[:50]}...")
            print(f"   💬 Ответ: {answer[:50]}...")
            if session_id:
                print(f"   🔑 Session: {session_id} {'(новая)' if is_new_session else '(продолжение)'}")
            if token_stats:
                print(f"   📊 Токены: {token_stats.get('total_tokens', 0)}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки письма: {e}")
            return False

    def process_email(self, email_data: Dict) -> bool:
        """Обработка одного письма"""
        try:
            question = email_data.get('question', '')
            from_addr = email_data.get('from', '')
            subject = email_data.get('subject', '')
            email_id = email_data.get('id', '')
            
            if not question:
                self.logger.warning("Пустой вопрос, пропускаю")
                return False
            
            # Проверяем фильтры (они уже применены в email_reader, но дублируем для надежности)
            filters = self.config.get('filters', {})
            subject_contains = filters.get('subject_contains', [])
            
            if subject_contains:
                has_keyword = False
                for keyword in subject_contains:
                    if keyword.lower() in subject.lower():
                        has_keyword = True
                        break
                
                if not has_keyword:
                    self.logger.warning(f"⏭️  Письмо от {from_addr} не прошло фильтр: в теме '{subject}' нет обязательных слов {subject_contains}")
                    return False
            
            print(f"\n📧 Обработка письма от {from_addr}")
            print(f"📝 Тема: {subject if subject else '(пусто)'}")
            print(f"❓ Вопрос: {question[:100]}...")
            
            self.logger.info(f"Обработка письма от {from_addr}")
            
            # Обрабатываем вопрос с управлением сессией
            answer, session_id, is_new_session = self.process_question_with_session(
                question=question,
                from_addr=from_addr,
                subject=subject
            )
            
            if answer:
                print(f"✅ Получен ответ ({len(answer)} символов)")
                self.logger.info(f"✅ Получен ответ от DeepSeek ({len(answer)} символов)")
                
                # ===== ПОЛУЧАЕМ СТАТИСТИКУ ТОКЕНОВ =====
                token_stats = None
                if hasattr(self.deepseek, 'last_usage') and self.deepseek.last_usage:
                    token_stats = self.deepseek.last_usage
                    self.logger.info(f"📊 Токены: prompt={token_stats.get('prompt_tokens', 0)}, completion={token_stats.get('completion_tokens', 0)}, total={token_stats.get('total_tokens', 0)}")
                
                # Сохраняем ответ в файл с информацией о сессии
                processing_config = self.config.get('processing', {})
                if processing_config.get('save_responses', True):
                    self.save_response(email_data, question, answer, session_id, token_stats)
                
                # Отправляем ответ с session_id в теме
                self.email_sender.send_response(
                    to_email=from_addr,
                    question=question,
                    answer=answer,
                    original_subject=subject,
                    session_id=session_id,
                    is_new_session=is_new_session,
                    token_stats=token_stats  # <-- ПЕРЕДАЕМ ТОКЕНЫ
                )
                
                if self.email_reader.imap:
                    self.email_reader.move_to_folder(
                        email_data['id'],
                        self.config['email'].get('processed_folder', 'Processed')
                    )
                
                self.stats['processed'] += 1
                return True
            else:
                print("❌ Не удалось получить ответ от DeepSeek")
                self.logger.error("❌ Не удалось получить ответ от DeepSeek")
                self.stats['errors'] += 1
                return False
                
        except Exception as e:
            print(f"❌ Ошибка обработки письма: {e}")
            self.logger.error(f"❌ Ошибка обработки письма: {e}")
            self.stats['errors'] += 1
            import traceback
            traceback.print_exc()
            return False
    
    def save_response(self, email_data: Dict, question: str, answer: str, session_id: Optional[str] = None, token_stats: Optional[Dict] = None):
        """Сохранение ответа в файл"""
        try:
            processing_config = self.config.get('processing', {})
            output_dir = Path(processing_config.get('output_dir', 'email_responses'))
            json_dir = Path(processing_config.get('json_dir', 'email_responses/json'))
            
            output_dir.mkdir(exist_ok=True, parents=True)
            json_dir.mkdir(exist_ok=True, parents=True)
            
            safe_name = self.sanitize_filename(question)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{safe_name}"
            
            if processing_config.get('save_json', True):
                json_data = {
                    'timestamp': datetime.now().isoformat(),
                    'from': email_data.get('from', ''),
                    'subject': email_data.get('subject', ''),
                    'question': question,
                    'answer': answer,
                    'session_id': session_id,
                    'stats': self.stats,
                    'token_stats': token_stats 
                }
                json_path = json_dir / f"{filename}.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                print(f"   💾 Сохранено JSON: {json_path}")
            
            if processing_config.get('save_md', True):
                md_content = [
                    f"# Ответ на письмо от {email_data.get('from', 'Unknown')}",
                    "",
                    f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"**Тема:** {email_data.get('subject', '')}",
                    f"**Session ID:** {session_id or 'Нет сессии'}",
                    "",
                    "## ❓ Вопрос",
                    "",
                    question,
                    "",
                    "## 💬 Ответ",
                    "",
                    answer,
                    "",
                    "---",
                    f"*Обработано: {datetime.now().isoformat()}*"
                ]
                md_path = output_dir / f"{filename}.md"
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(md_content))
                print(f"   💾 Сохранено MD: {md_path}")
                
        except Exception as e:
            print(f"⚠️  Ошибка сохранения ответа: {e}")
    
    def sanitize_filename(self, text: str, max_len: int = 50) -> str:
        """Создание безопасного имени файла"""
        import re
        text = ' '.join(text.split())[:max_len]
        text = re.sub(r'[<>:"/\\|?*]', '_', text)
        return text.rstrip('.') or 'empty'
    
    def process_batch_file(self, file_path: Path) -> bool:
        """
        Обработка одного файла из папки requests
        
        Args:
            file_path: Путь к файлу с запросом
            
        Returns:
            True если успешно обработано
        """
        try:
            # Читаем файл
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                self.logger.warning(f"Пустой файл: {file_path}")
                return False
            
            # Парсим содержимое
            # Поддерживаем форматы:
            # 1. Простой текст - весь файл как вопрос
            # 2. JSON с полями question, session_id, from
            # 3. Текст с метаданными в начале
            
            question = content
            session_id = None
            from_addr = file_path.stem  # Имя файла как идентификатор
            
            # Пробуем распарсить как JSON
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    question = data.get('question', data.get('query', data.get('text', '')))
                    session_id = data.get('session_id', data.get('sessionId', None))
                    from_addr = data.get('from', data.get('sender', file_path.stem))
            except json.JSONDecodeError:
                # Не JSON, пробуем другие форматы
                lines = content.split('\n')
                if len(lines) > 1:
                    # Проверяем, есть ли метаданные в формате "key: value"
                    first_line = lines[0].strip()
                    if ':' in first_line:
                        # Пробуем найти session_id и отправителя
                        for line in lines[:5]:  # Проверяем первые 5 строк
                            if 'session' in line.lower() or 'sid' in line.lower():
                                parts = line.split(':', 1)
                                if len(parts) == 2:
                                    session_id = parts[1].strip()
                            if 'from' in line.lower() or 'sender' in line.lower():
                                parts = line.split(':', 1)
                                if len(parts) == 2:
                                    from_addr = parts[1].strip()
                        
                        # Остальное - вопрос
                        question = '\n'.join(lines[1:]) if len(lines) > 1 else content
            
            if not question:
                self.logger.warning(f"Не удалось извлечь вопрос из {file_path}")
                return False
            
            print(f"\n📁 Обработка файла: {file_path.name}")
            print(f"   От: {from_addr}")
            print(f"   Session: {session_id or 'Нет'}")
            print(f"   Вопрос: {question[:100]}...")
            
            self.logger.info(f"Обработка файла {file_path.name} от {from_addr}")
            
            # Обрабатываем вопрос с управлением сессией
            answer, new_session_id, is_new_session = self.process_question_with_session(
                question=question,
                from_addr=from_addr,
                subject=f"Batch: {file_path.name}",
                session_id=session_id
            )
            
            if answer:
                print(f"✅ Получен ответ ({len(answer)} символов)")
                self.logger.info(f"✅ Получен ответ от DeepSeek ({len(answer)} символов)")
                
                # Сохраняем ответ
                batch_config = self.config.get('batch', {})
                output_dir = Path(batch_config.get('output_dir', 'responses'))
                json_dir = Path(batch_config.get('json_dir', 'responses/json'))
                
                output_dir.mkdir(exist_ok=True, parents=True)
                json_dir.mkdir(exist_ok=True, parents=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                base_name = file_path.stem
                
                # Сохраняем JSON
                if batch_config.get('save_json', True):
                    json_data = {
                        'timestamp': datetime.now().isoformat(),
                        'from': from_addr,
                        'file': file_path.name,
                        'question': question,
                        'answer': answer,
                        'session_id': new_session_id,
                        'is_new_session': is_new_session,
                        'stats': self.stats
                    }
                    json_path = json_dir / f"{timestamp}_{base_name}.json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)
                    print(f"   💾 Сохранено JSON: {json_path}")
                
                # Сохраняем MD
                if batch_config.get('save_md', True):
                    md_content = [
                        f"# Ответ на запрос из {file_path.name}",
                        "",
                        f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        f"**От:** {from_addr}",
                        f"**Session ID:** {new_session_id or 'Нет сессии'}",
                        f"**Новая сессия:** {'Да' if is_new_session else 'Нет'}",
                        "",
                        "## ❓ Вопрос",
                        "",
                        question,
                        "",
                        "## 💬 Ответ",
                        "",
                        answer,
                        "",
                        "---",
                        f"*Обработано: {datetime.now().isoformat()}*"
                    ]
                    md_path = output_dir / f"{timestamp}_{base_name}.md"
                    with open(md_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(md_content))
                    print(f"   💾 Сохранено MD: {md_path}")
                
                # Перемещаем обработанный файл
                processed_dir = output_dir / 'processed'
                processed_dir.mkdir(exist_ok=True)
                processed_path = processed_dir / file_path.name
                file_path.rename(processed_path)
                print(f"   📁 Файл перемещен в processed/")
                
                self.stats['processed'] += 1
                return True
            else:
                print("❌ Не удалось получить ответ от DeepSeek")
                self.logger.error(f"❌ Не удалось получить ответ для {file_path}")
                self.stats['errors'] += 1
                return False
                
        except Exception as e:
            print(f"❌ Ошибка обработки файла {file_path}: {e}")
            self.logger.error(f"❌ Ошибка обработки файла {file_path}: {e}")
            self.stats['errors'] += 1
            import traceback
            traceback.print_exc()
            return False
    
    def run_batch_processing(self) -> int:
        """Пакетная обработка файлов из папки requests"""
        if not self.config.get('general', {}).get('enable_batch_processing', False):
            return 0
        
        batch_config = self.config.get('batch', {})
        input_dir = Path(batch_config.get('input_dir', 'requests'))
        
        if not input_dir.exists():
            return 0
        
        # Ищем файлы для обработки
        files = list(input_dir.glob('*'))
        if not files:
            return 0
        
        # Фильтруем только файлы (не папки)
        files = [f for f in files if f.is_file()]
        
        # Исключаем уже обработанные (если есть маркер)
        files = [f for f in files if not f.suffix == '.processed']
        
        if not files:
            return 0
        
        max_files = self.config.get('general', {}).get('max_batch_files', 10)
        if len(files) > max_files:
            files = files[:max_files]
            self.logger.info(f"Ограничение на обработку: {max_files} файлов")
        
        print(f"\n📁 Найдено файлов для пакетной обработки: {len(files)}")
        self.logger.info(f"📁 Найдено файлов для пакетной обработки: {len(files)}")
        
        processed = 0
        for file_path in files:
            if self.process_batch_file(file_path):
                processed += 1
            delay = self.config.get('general', {}).get('delay_between_requests', 0.5)
            time.sleep(delay)
        
        return processed
    
    def run_email_processing(self) -> int:
        """Одноразовая проверка почты"""
        if not self.config.get('general', {}).get('enable_email_processing', True):
            return 0
        
        print("\n📧 Проверка почты...")
        self.logger.info("📧 Проверка почты...")
        
        if not self.email_reader.connect():
            print("❌ Не удалось подключиться к почте")
            self.logger.error("❌ Не удалось подключиться к почте")
            return 0
        
        try:
            max_emails = self.config.get('general', {}).get('max_emails_per_check', 5)
            emails = self.email_reader.get_emails(limit=max_emails)
            
            if not emails:
                print("📭 Новых писем нет")
                self.logger.info("📭 Новых писем нет")
                return 0
            
            print(f"📨 Найдено новых писем: {len(emails)}")
            self.logger.info(f"📨 Найдено новых писем: {len(emails)}")
            
            if not self.email_sender.connect():
                print("❌ Не удалось подключиться к SMTP")
                self.logger.error("❌ Не удалось подключиться к SMTP")
                return 0
            
            processed = 0
            for email_data in emails:
                if self.process_email(email_data):
                    processed += 1
                delay = self.config.get('general', {}).get('delay_between_requests', 0.5)
                time.sleep(delay)
            
            return processed
            
        finally:
            self.email_reader.disconnect()
            self.email_sender.disconnect()
    
    def run_once(self) -> int:
        """Одноразовая проверка"""
        total = 0
        total += self.run_email_processing()
        total += self.run_batch_processing()
        return total
    
    def run_forever(self):
        """Бесконечный цикл с выбором режима ожидания"""
        general = self.config.get('general', {})
        wait_mode = general.get('email_wait_mode', 'polling')
        
        print("🚀 Запуск почтового моста")
        print(f"📧 Почта: {self.config.get('email', {}).get('username', '')}")
        print(f"🤖 Модель: {self.config.get('deepseek', {}).get('model', 'deepseek-chat')}")
        print(f"📡 Режим ожидания: {wait_mode}")
        print("="*50)
        
        if wait_mode == 'idle':
            self._run_idle_mode()
        elif wait_mode == 'hybrid':
            self._run_hybrid_mode()
        else:
            self._run_polling_mode()

def main():
    """Точка входа"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("""
Использование: python src/email_bridge.py [опции]

Опции:
  --once    - Одноразовая проверка почты и пакетов
  --help    - Показать справку

Конфигурация:
  config/config.yaml  - Основной конфиг (публичная часть)
  config/secrets.yaml - Секреты (НЕ в git!)

Пакетная обработка:
  Поместите файлы с запросами в папку requests/
  Поддерживаемые форматы:
    - Простой текст (весь файл как вопрос)
    - JSON с полями question, session_id, from
    - Текст с метаданными в первых строках
        """)
        return
    
    bridge = EmailBridge()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        bridge.run_once()
    else:
        bridge.run_forever()


if __name__ == "__main__":
    main()