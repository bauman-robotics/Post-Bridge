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
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

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
            'started': datetime.now().isoformat()
        }
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        print("\n🛑 Получен сигнал завершения. Останавливаюсь...")
        if hasattr(self, 'logger'):
            self.logger.info("🛑 Получен сигнал завершения")
        self.running = False
    
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
                    
                    # Если есть другие секреты - можно добавить
                    # if secrets and 'deepseek' in secrets:
                    #     config['deepseek'].update(secrets['deepseek'])
                    
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
    
    def print_config(self):
        """Вывод конфигурации в консоль и лог"""
        print("\n" + "="*70)
        print("🚀 ЗАПУСК ПОЧТОВОГО МОСТА")
        print("="*70)
        
        general = self.config.get('general', {})
        print("\n⚙️  ОБЩИЕ НАСТРОЙКИ:")
        print(f"   Режим: {general.get('mode', 'server')}")
        print(f"   Обработка почты: {'✅ Включена' if general.get('enable_email_processing', True) else '❌ Отключена'}")
        print(f"   Интервал проверки: {general.get('email_check_interval', 60)} сек")
        
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
        
        filters = self.config.get('filters', {})
        print("\n🔍 ФИЛЬТРЫ:")
        subject_contains = filters.get('subject_contains', [])
        if subject_contains:
            print(f"   ✅ Обязательные слова в теме: {subject_contains}")
        else:
            print(f"   ❌ Обязательные слова в теме: НЕ УСТАНОВЛЕНЫ")
        
        print("\n" + "="*70)
        print("✅ Почтовый мост запущен!")
        print("="*70 + "\n")
        
        # Записываем в лог
        self.logger.info("="*70)
        self.logger.info("🚀 ЗАПУСК ПОЧТОВОГО МОСТА")
        self.logger.info("="*70)
        self.logger.info(f"🤖 DeepSeek API: {deepseek.get('api_url', 'http://localhost:8000')}")
        self.logger.info(f"📧 Email: {email.get('username', 'Не указан')}")
        self.logger.info("="*70)
    
    def process_email(self, email_data: Dict) -> bool:
        """Обработка одного письма"""
        try:
            question = email_data.get('question', '')
            from_addr = email_data.get('from', '')
            subject = email_data.get('subject', '')
            
            if not question:
                self.logger.warning("Пустой вопрос, пропускаю")
                return False
            
            # Проверяем фильтры
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
            
            answer = self.deepseek.ask(question)
            
            if answer:
                print(f"✅ Получен ответ ({len(answer)} символов)")
                self.logger.info(f"✅ Получен ответ от DeepSeek ({len(answer)} символов)")
                
                if self.config.get('processing', {}).get('save_responses', True):
                    self.save_response(email_data, question, answer)
                
                self.email_sender.send_response(
                    to_email=from_addr,
                    question=question,
                    answer=answer,
                    original_subject=subject
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
            return False
    
    def save_response(self, email_data: Dict, question: str, answer: str):
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
                    'stats': self.stats
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
        return self.run_email_processing()
    
    def run_forever(self):
        """Бесконечный цикл проверки почты"""
        general = self.config.get('general', {})
        email_interval = general.get('email_check_interval', 60)
        
        print("🚀 Запуск почтового моста")
        print(f"📧 Почта: {self.config.get('email', {}).get('username', '')}")
        print(f"🤖 Модель: {self.config.get('deepseek', {}).get('model', 'deepseek-chat')}")
        print("="*50)
        
        while self.running:
            try:
                self.run_email_processing()
                
                for _ in range(email_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
                self.logger.error(f"❌ Ошибка в основном цикле: {e}")
                time.sleep(10)
        
        print("\n📊 ИТОГОВАЯ СТАТИСТИКА")
        print(f"   Обработано писем: {self.stats['processed']}")
        print(f"   Ошибок: {self.stats['errors']}")
        print(f"   Запущен: {self.stats['started']}")
        self.logger.info("📊 ИТОГОВАЯ СТАТИСТИКА")
        self.logger.info(f"   Обработано писем: {self.stats['processed']}")
        self.logger.info(f"   Ошибок: {self.stats['errors']}")
        print("👋 Завершение работы")
        self.logger.info("👋 Завершение работы")


def main():
    """Точка входа"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("""
Использование: python src/email_bridge.py [опции]

Опции:
  --once    - Одноразовая проверка почты
  --help    - Показать справку

Конфигурация:
  config/config.yaml  - Основной конфиг (публичная часть)
  config/secrets.yaml - Секреты (НЕ в git!)
        """)
        return
    
    bridge = EmailBridge()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        bridge.run_once()
    else:
        bridge.run_forever()


if __name__ == "__main__":
    main()