#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для чтения почты
Извлекает письма и преобразует их в запросы
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import re

# Импортируем логгер
from logger import get_logger

class EmailReader:
    """Класс для чтения писем"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.imap = None
        self.logger = get_logger()
        
    def connect(self) -> bool:
        try:
            self.logger.info(f"Подключение к IMAP серверу {self.config['imap_server']}")
            self.imap = imaplib.IMAP4_SSL(self.config['imap_server'])
            self.imap.login(self.config['username'], self.config['password'])
            self.imap.select(self.config.get('check_folder', 'INBOX'))
            self.logger.info("✅ Успешное подключение к почте")
            return True
        except Exception as e:
            self.logger.error(f"❌ Ошибка подключения к почте: {e}")
            return False
    
    def disconnect(self):
        if self.imap:
            try:
                self.imap.close()
                self.imap.logout()
                self.logger.debug("Отключение от почтового сервера")
            except:
                pass
            self.imap = None
    
    def decode_header_value(self, header: str) -> str:
        if not header:
            return ""
        decoded_parts = decode_header(header)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                try:
                    if charset:
                        part = part.decode(charset)
                    else:
                        part = part.decode('utf-8', errors='ignore')
                except:
                    part = part.decode('utf-8', errors='ignore')
            result.append(str(part))
        return ' '.join(result)
    
    def get_email_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body += payload.decode(charset, errors='ignore')
                    except Exception as e:
                        self.logger.debug(f"Ошибка декодирования части письма: {e}")
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
            except Exception as e:
                self.logger.debug(f"Ошибка декодирования письма: {e}")
                body = str(msg.get_payload())
        return body.strip()
    
    def clean_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract_question(self, body: str) -> str:
        clean_body = self.clean_html(body)
        markers = [
            r'(?:Вопрос|Question|Запрос|Query)\s*[:;]\s*(.+?)(?:\n\n|\Z)',
            r'(?:Спроси|Ask|Спросить)\s*(.+?)(?:\n\n|\Z)',
            r'[:;]\s*(.+?)(?:\n\n|\Z)',
        ]
        for pattern in markers:
            match = re.search(pattern, clean_body, re.IGNORECASE | re.DOTALL)
            if match:
                question = match.group(1).strip()
                if question and len(question) > 5:
                    return question
        lines = [line.strip() for line in clean_body.split('\n') if line.strip()]
        if lines:
            if len(lines[0]) > 10:
                return lines[0]
            return ' '.join(lines[:3])
        return clean_body[:500] if clean_body else body[:500]
    
    def passes_filters(self, subject: str, from_addr: str, body: str = "") -> Tuple[bool, str]:
        """
        Проверка фильтров для письма
        """
        filters = self.config.get('filters', {})
        
        # ===== ЖЕСТКАЯ ПРОВЕРКА: пустая тема =====
        subject_contains = filters.get('subject_contains', [])
        if subject_contains:
            # Если тема пустая или состоит только из пробелов
            if not subject or not subject.strip():
                return False, f"Тема письма пуста, а требуется одно из слов: {subject_contains}"
            
            # Проверяем наличие ключевых слов
            has_keyword = False
            matched_keyword = None
            subject_lower = subject.lower()
            for keyword in subject_contains:
                if keyword.lower() in subject_lower:
                    has_keyword = True
                    matched_keyword = keyword
                    break
            
            if not has_keyword:
                return False, f"В теме нет обязательных слов: {subject_contains}"
            else:
                self.logger.debug(f"Найдено ключевое слово в теме: '{matched_keyword}'")
        
        # Проверка черного списка отправителей
        blacklist = filters.get('from_blacklist', [])
        if blacklist:
            for blocked in blacklist:
                if blocked.lower() in from_addr.lower():
                    return False, f"Отправитель в черном списке: {blocked}"
        
        # Проверка белого списка отправителей
        whitelist = filters.get('from_whitelist', [])
        if whitelist:
            allowed = False
            for allowed_addr in whitelist:
                if allowed_addr.lower() in from_addr.lower():
                    allowed = True
                    break
            if not allowed:
                return False, "Отправитель не в белом списке"
        
        # Проверка отсутствия ключевых слов в теме
        subject_not_contains = filters.get('subject_not_contains', [])
        if subject_not_contains:
            subject_lower = subject.lower()
            for forbidden in subject_not_contains:
                if forbidden.lower() in subject_lower:
                    return False, f"В теме есть запрещенное слово: '{forbidden}'"
        
        # Проверка наличия ключевых слов в теле письма
        body_contains = filters.get('body_contains', [])
        if body_contains and body:
            has_keyword = False
            matched_keyword = None
            clean_body = self.clean_html(body).lower()
            for keyword in body_contains:
                if keyword.lower() in clean_body:
                    has_keyword = True
                    matched_keyword = keyword
                    break
            if not has_keyword:
                return False, f"В теле нет обязательных слов: {body_contains}"
            else:
                self.logger.debug(f"Найдено ключевое слово в теле: '{matched_keyword}'")
        
        return True, "OK"
    
    def get_emails(self, limit: Optional[int] = None) -> List[Dict]:
        if not self.imap and not self.connect():
            return []
        
        emails = []
        filtered_count = 0
        error_count = 0
        total_count = 0
        
        try:
            status, messages = self.imap.search(None, 'UNSEEN')
            
            if status != 'OK' or not messages[0]:
                self.logger.debug("Новых непрочитанных писем нет")
                return []
            
            email_ids = messages[0].split()
            total_count = len(email_ids)
            self.logger.info(f"📨 Найдено непрочитанных писем: {total_count}")
            
            if limit and len(email_ids) > limit:
                email_ids = email_ids[-limit:]
                self.logger.debug(f"Ограничение на обработку: {limit} писем")
            
            for email_id in reversed(email_ids):
                try:
                    status, msg_data = self.imap.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK' or not msg_data:
                        error_count += 1
                        continue
                    
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    subject = self.decode_header_value(msg.get('Subject', ''))
                    from_addr = self.decode_header_value(msg.get('From', ''))
                    date_str = msg.get('Date', '')
                    
                    try:
                        date = parsedate_to_datetime(date_str)
                    except:
                        date = datetime.now()
                    
                    body = self.get_email_body(msg)
                    question = self.extract_question(body)
                    
                    subject_display = subject[:50] + "..." if len(subject) > 50 else subject
                    self.logger.debug(f"Обработка письма от {from_addr} | Тема: '{subject_display}'")
                    
                    # ===== ОТЛАДОЧНЫЙ ВЫВОД =====
                    self.logger.debug(f"   🔍 Проверка фильтров...")
                    self.logger.debug(f"   ⚙️  Фильтр subject_contains: {self.config.get('filters', {}).get('subject_contains', [])}")
                    
                    # Проверяем фильтры
                    passes, reason = self.passes_filters(subject, from_addr, body)
                    
                    if not passes:
                        filtered_count += 1
                        self.logger.email_processed(from_addr, subject, "FILTERED", reason)
                        self.logger.debug(f"   ⏭️  Письмо ОТФИЛЬТРОВАНО: {reason}")
                        
                        if self.config.get('mark_as_read', True):
                            self.imap.store(email_id, '+FLAGS', '\\Seen')
                        
                        filtered_folder = self.config.get('filtered_folder')
                        if filtered_folder:
                            try:
                                self.imap.create(filtered_folder)
                                self.imap.copy(email_id, filtered_folder)
                                if self.config.get('delete_after_filtering', False):
                                    self.imap.store(email_id, '+FLAGS', '\\Deleted')
                                self.logger.debug(f"   📁 Письмо перемещено в '{filtered_folder}'")
                            except Exception as e:
                                self.logger.debug(f"   ⚠️  Ошибка перемещения: {e}")
                        
                        continue
                    
                    self.logger.email_processed(from_addr, subject, "PROCESSED")
                    question_display = question[:50] + "..." if len(question) > 50 else question
                    self.logger.debug(f"✅ Письмо ПРОШЛО фильтры. Вопрос: '{question_display}'")
                    
                    emails.append({
                        'id': email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                        'subject': subject,
                        'from': from_addr,
                        'date': date,
                        'body': body,
                        'question': question,
                        'raw_message': msg
                    })
                    
                    if self.config.get('mark_as_read', True):
                        self.imap.store(email_id, '+FLAGS', '\\Seen')
                    
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Ошибка обработки письма {email_id}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения писем: {e}")
        
        self.logger.info(f"📊 Статистика: Всего {total_count} | Обработано {len(emails)} | Отфильтровано {filtered_count} | Ошибок {error_count}")
        
        return emails
    
    def move_to_folder(self, email_id: str, folder: str):
        if not self.imap:
            return
        try:
            self.imap.create(folder)
            self.imap.copy(email_id, folder)
            if self.config.get('delete_after_processing', False):
                self.imap.store(email_id, '+FLAGS', '\\Deleted')
            self.logger.debug(f"Письмо перемещено в '{folder}'")
        except Exception as e:
            self.logger.warning(f"Ошибка перемещения письма в '{folder}': {e}")


if __name__ == "__main__":
    import yaml
    
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    if 'email' not in config:
        config['email'] = {}
    if 'filters' not in config:
        config['filters'] = {}
    
    reader = EmailReader(config['email'])
    
    if reader.connect():
        emails = reader.get_emails(limit=3)
        print(f"\n📊 Найдено писем после фильтрации: {len(emails)}")
        
        for email_data in emails:
            print(f"\n📧 От: {email_data['from']}")
            print(f"📝 Тема: {email_data['subject']}")
            print(f"❓ Вопрос: {email_data['question'][:100]}...")
        
        reader.disconnect()