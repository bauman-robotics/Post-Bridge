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
import time
import socket

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
            
            # Устанавливаем таймаут на соединение
            socket.setdefaulttimeout(30)  # 30 секунд таймаут
            
            self.imap = imaplib.IMAP4_SSL(self.config['imap_server'])
            self.imap.login(self.config['username'], self.config['password'])
            self.imap.select(self.config.get('check_folder', 'INBOX'))
            self.logger.info("✅ Успешное подключение к почте")
            
            # Сбрасываем таймаут
            socket.setdefaulttimeout(None)
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

    def is_connected(self) -> bool:
        """Проверка, живо ли IMAP соединение"""
        if not self.imap:
            return False
        try:
            self.imap.noop() # Отправляем пустую команд
            return True
        except:
            return False

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
    
    def clean_email_body(self, body: str) -> str:
        """
        Очистка тела письма от цитат и метаданных
        """
        if not body:
            return body
        
        lines = body.split('\n')
        clean_lines = []
        skip_quote = False
        found_new_question = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Пропускаем пустые строки в начале
            if not line_stripped and not clean_lines and not found_new_question:
                continue
            
            # ===== ПРОПУСКАЕМ ЦИТАТЫ =====
            # Строки-цитаты (начинаются с >)
            if line_stripped.startswith('>'):
                continue
            
            # Строки с "On ... wrote:"
            if re.match(r'^On .+ wrote:', line_stripped):
                skip_quote = True
                continue
            
            # ===== ПРОПУСКАЕМ ЗАГОЛОВКИ =====
            if re.match(r'^(От|From|Sent|To|Subject|Date|Тема|Отправитель|Кому|Дата|Cc|Bcc):', line_stripped, re.IGNORECASE):
                continue
            
            # ===== ПРОПУСКАЕМ РАЗДЕЛИТЕЛИ =====
            if re.match(r'^[-_]{3,}$', line_stripped):
                skip_quote = True
                continue
            
            # ===== ПРОПУСКАЕМ МАРКЕРЫ ПИСЕМ БОТА =====
            # Удаляем строки с эмодзи-маркерами из писем бота
            if any(marker in line_stripped for marker in [
                '📝 **Ваш вопрос:**',
                '💬 **Ответ:**',
                '🆕 Начата новая сессия',
                '🔄 Продолжение сессии',
                'автоматический ответ от DeepSeek',
                'Это автоматический ответ от DeepSeek AI',
                'Если у вас есть дополнительные вопросы'
            ]):
                skip_quote = True
                continue
            
            # Удаляем строки с датой в формате "DD.MM.YYYY HH:MM"
            if re.search(r'\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}', line_stripped):
                if skip_quote or '📅' in line_stripped:
                    continue
            
            # ===== ПРОВЕРЯЕМ, НЕ НАЧАЛСЯ ЛИ НОВЫЙ ВОПРОС =====
            # Если строка не является цитатой и длиннее 10 символов,
            # и это не маркер бота - это может быть новый вопрос
            if not skip_quote and len(line_stripped) > 10:
                # Если мы нашли потенциальный вопрос, сбрасываем skip_quote
                found_new_question = True
            
            # Если мы в режиме пропуска и встретили пустую строку - возможно конец цитаты
            if skip_quote and not line_stripped:
                # Не сбрасываем skip_quote полностью, а проверяем следующую строку
                continue
            
            # Если строка начинается с "##" - это маркдаун заголовок из цитаты
            if line_stripped.startswith('##') and skip_quote:
                continue
            
            # Добавляем строку, если она не в режиме пропуска
            if not skip_quote:
                clean_lines.append(line)
        
        # Удаляем лишние пустые строки
        result = '\n'.join(clean_lines).strip()
        
        # Если после очистки ничего не осталось, возвращаем исходный текст
        if not result:
            return body
        
        return result
    
    # Без очистки истории 
    def extract_question(self, body: str) -> str:
        """
        Извлечение вопроса из тела письма.
        Возвращает ВЕСЬ текст письма как есть.
        """
        if not body:
            return ""
        
        # Просто удаляем HTML (чтобы не было тегов)
        clean_body = self.clean_html(body)
        
        # Возвращаем ВЕСЬ текст
        return clean_body.strip() if clean_body else body.strip()

    def extract_session_id(self, subject: str) -> Optional[str]:
        """Извлечение session_id из темы письма"""
        if not subject:
            return None
        match = re.search(r'\[SID:([a-zA-Z0-9\-_:]+)\]', subject)
        if match:
            return match.group(1)
        return None
    
    def passes_filters(self, subject: str, from_addr: str, body: str = "") -> Tuple[bool, str]:
        """Проверка фильтров для письма"""
        filters = self.config.get('filters', {})
        
        # Проверка по теме
        subject_contains = filters.get('subject_contains', [])
        if subject_contains:
            if not subject or not subject.strip():
                return False, f"Тема письма пуста, а требуется одно из слов: {subject_contains}"
            
            has_keyword = False
            subject_lower = subject.lower()
            for keyword in subject_contains:
                if keyword.lower() in subject_lower:
                    has_keyword = True
                    break
            
            if not has_keyword:
                return False, f"В теме нет обязательных слов: {subject_contains}"
        
        # Проверка черного списка
        blacklist = filters.get('from_blacklist', [])
        if blacklist:
            for blocked in blacklist:
                if blocked.lower() in from_addr.lower():
                    return False, f"Отправитель в черном списке: {blocked}"
        
        # Проверка белого списка
        whitelist = filters.get('from_whitelist', [])
        if whitelist:
            allowed = False
            for allowed_addr in whitelist:
                if allowed_addr.lower() in from_addr.lower():
                    allowed = True
                    break
            if not allowed:
                return False, "Отправитель не в белом списке"
        
        # Проверка запрещенных слов в теме
        subject_not_contains = filters.get('subject_not_contains', [])
        if subject_not_contains:
            subject_lower = subject.lower()
            for forbidden in subject_not_contains:
                if forbidden.lower() in subject_lower:
                    return False, f"В теме есть запрещенное слово: '{forbidden}'"
        
        return True, "OK"
    
    def get_emails(self, limit: Optional[int] = None) -> List[Dict]:
        """Получение писем из почтового ящика"""
        if not self.imap and not self.connect():
            return []
        
        emails = []
        filtered_count = 0
        error_count = 0
        total_count = 0
        
        try:
            # Устанавливаем таймаут на операцию
            socket.setdefaulttimeout(30)
            
            self.logger.debug("📡 Поиск непрочитанных писем...")
            status, messages = self.imap.search(None, 'UNSEEN')
            
            socket.setdefaulttimeout(None)
            
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
                    
                    session_id = self.extract_session_id(subject)
                    
                    subject_display = subject[:50] + "..." if len(subject) > 50 else subject
                    self.logger.debug(f"Обработка письма от {from_addr} | Тема: '{subject_display}'")
                    if session_id:
                        self.logger.debug(f"   🔑 Session ID: {session_id}")
                    
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
                        'session_id': session_id,
                        'raw_message': msg
                    })
                    
                    if self.config.get('mark_as_read', True):
                        self.imap.store(email_id, '+FLAGS', '\\Seen')
                    
                except socket.timeout:
                    self.logger.error(f"⏰ Таймаут при обработке письма {email_id}")
                    error_count += 1
                    continue
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Ошибка обработки письма {email_id}: {e}")
                    continue
            
        except socket.timeout:
            self.logger.error("⏰ Таймаут IMAP операции, переподключаюсь...")
            self.disconnect()
            self.connect()
            return []
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения писем: {e}")
            return []
        
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

    def wait_for_new_emails(self, timeout: int = 60, stop_check=None) -> bool:
        """
        Ожидание новых писем.
        
        Args:
            timeout: Максимальное время ожидания в секундах
            stop_check: Функция для проверки флага остановки
            
        Returns:
            True если есть новые письма, False если нет
        """
        if not self.imap:
            return False
        
        try:
            self.imap.select(self.config.get('check_folder', 'INBOX'))
            
            # Быстрая проверка
            status, messages = self.imap.search(None, 'UNSEEN')
            if status == 'OK' and messages[0]:
                return True
            
            # Ожидание с проверкой флага
            start_time = time.time()
            while time.time() - start_time < timeout:
                # Проверяем флаг остановки
                if stop_check and not stop_check():
                    self.logger.debug("🛑 Остановка по флагу")
                    return False
                
                # Проверяем новые письма
                status, messages = self.imap.search(None, 'UNSEEN')
                if status == 'OK' and messages[0]:
                    return True
                
                time.sleep(2)
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка: {e}")
            return False