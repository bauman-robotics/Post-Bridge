#!/usr/bin/env python3
"""
Восстановление писем из папки Filtered
Запускать вручную для диагностики
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import yaml
import imaplib
from email.header import decode_header

def decode_header_value(header):
    if not header:
        return ""
    parts = decode_header(header)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                part = part.decode(charset or 'utf-8', errors='ignore')
            except:
                part = part.decode('utf-8', errors='ignore')
        result.append(str(part))
    return ' '.join(result)

def main():
    print("🔍 ВОССТАНОВЛЕНИЕ ПИСЕМ ИЗ FILTERED")
    print("="*70)
    
    # Загружаем секреты
    with open('config/secrets.yaml', 'r') as f:
        secrets = yaml.safe_load(f)
    
    email_config = secrets.get('email', {})
    
    print(f"📧 Подключение к {email_config.get('imap_server', 'imap.yandex.ru')}")
    print(f"👤 Пользователь: {email_config.get('username', '')}")
    
    try:
        imap = imaplib.IMAP4_SSL(email_config.get('imap_server', 'imap.yandex.ru'))
        imap.login(email_config['username'], email_config['password'])
        print("✅ Подключено")
        
        # Проверяем папки
        for folder in ['Filtered', 'Errors']:
            try:
                imap.select(folder)
                status, messages = imap.search(None, 'ALL')
                if status == 'OK' and messages[0]:
                    count = len(messages[0].split())
                    print(f"\n📁 Папка '{folder}': {count} писем")
                    
                    # Показываем содержимое
                    for i, email_id in enumerate(messages[0].split()[:5], 1):
                        status, data = imap.fetch(email_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                        if status == 'OK':
                            header = data[0][1].decode()
                            from_line = [l for l in header.split('\n') if l.startswith('From:')]
                            subject_line = [l for l in header.split('\n') if l.startswith('Subject:')]
                            print(f"   {i}. От: {decode_header_value(from_line[0] if from_line else '?')}")
                            print(f"      Тема: {decode_header_value(subject_line[0] if subject_line else '?')}")
                    
                    if len(messages[0].split()) > 5:
                        print(f"   ... и еще {len(messages[0].split()) - 5} писем")
                    
                    # Спрашиваем, восстанавливать ли
                    answer = input(f"\n🔄 Восстановить все письма из '{folder}' в INBOX? (y/N): ")
                    if answer.lower() == 'y':
                        for email_id in messages[0].split():
                            imap.copy(email_id, 'INBOX')
                            imap.store(email_id, '+FLAGS', '\\Deleted')
                        imap.expunge()
                        print(f"✅ {count} писем восстановлены в INBOX")
                
            except Exception as e:
                print(f"⚠️ Ошибка работы с папкой '{folder}': {e}")
        
        imap.close()
        imap.logout()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()