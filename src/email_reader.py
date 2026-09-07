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
import json 

# Импортируем логгер
from logger import get_logger

class EmailReader:
    """Класс для чтения писем"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.imap = None
        self.logger = get_logger()
        
        # ===== ДОБАВИМ ДИАГНОСТИКУ =====
        self.diagnostics = {
            'total_emails': 0,
            'fetch_errors': 0,
            'filtered': 0,
            'filter_reasons': {},
            'empty_questions': 0,
            'processed': 0,
            'session_ids_found': 0,
            'emails_by_folder': {},
            'last_check': None
        }
        self.debug_file = Path("logs/email_diagnostics.json")
        self.debug_file.parent.mkdir(exist_ok=True)

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
            self.logger.error(f"⚠️ Ошибка подключения к почте: {e}")
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
        """
        Извлечение тела письма.
        Берет только text/plain, если нет - text/html.
        """
        body = ""
        
        if msg.is_multipart():
            # Сначала ищем text/plain
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        return body.strip()  # Возвращаем сразу, как нашли text/plain
                    except:
                        pass
            
            # Если text/plain нет - ищем text/html
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/html" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        return self.clean_html(body)  # Очищаем от HTML
                    except:
                        pass
        else:
            # Не multipart письмо
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
                return body.strip()
            except:
                body = str(msg.get_payload())
                return body.strip()
        
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
        """Получение писем с ДИАГНОСТИКОЙ"""
        if not self.imap and not self.connect():
            return []
        
        # Проверяем соединение
        try:
            self.imap.noop()
        except:
            self.logger.warning("⚠️ Соединение потеряно, переподключаюсь...")
            self.disconnect()
            if not self.connect():
                return []

        emails = []
        filtered_count = 0
        error_count = 0
        total_count = 0
        
        # ===== ДИАГНОСТИКА: логируем состояние папок =====
        #self.log_folder_status()
        
        try:
            socket.setdefaulttimeout(30)
            
            self.logger.debug("📡 Поиск непрочитанных писем...")
            status, messages = self.imap.search(None, 'UNSEEN')
            
            socket.setdefaulttimeout(None)
            
            if status != 'OK' or not messages[0]:
                self.logger.debug("Новых непрочитанных писем нет")
                # ===== ДИАГНОСТИКА: проверяем есть ли прочитанные =====
                self.check_all_emails_count()
                return []
            
            email_ids = messages[0].split()
            total_count = len(email_ids)
            self.logger.info(f"📨 Найдено непрочитанных писем: {total_count}")
            
            # ===== ДИАГНОСТИКА: логируем ID всех писем =====
            self.logger.debug(f"📋 ID писем: {[eid.decode() if isinstance(eid, bytes) else str(eid) for eid in email_ids]}")
            
            if limit and len(email_ids) > limit:
                email_ids = email_ids[-limit:]
                self.logger.debug(f"Ограничение на обработку: {limit} писем")
            
            for email_id in reversed(email_ids):
                email_id_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                
                # ===== ДИАГНОСТИКА: начало обработки письма =====
                self.logger.debug(f"🔍 Начало обработки письма {email_id_str}")
                
                try:
                    status, msg_data = self.imap.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK' or not msg_data:
                        error_count += 1
                        self.logger.error(f"❌ Не удалось получить письмо {email_id_str}: status={status}")
                        continue
                    
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    subject = self.decode_header_value(msg.get('Subject', ''))
                    from_addr = self.decode_header_value(msg.get('From', ''))
                    date_str = msg.get('Date', '')
                    
                    # ===== ДИАГНОСТИКА: информация о письме =====
                    self.logger.debug(f"📧 Письмо {email_id_str}:")
                    self.logger.debug(f"   От: {from_addr}")
                    self.logger.debug(f"   Тема: {subject}")
                    
                    try:
                        date = parsedate_to_datetime(date_str)
                    except:
                        date = datetime.now()
                    
                    body = self.get_email_body(msg)
                    question = self.extract_question(body)
                    
                    session_id = self.extract_session_id(subject)
                    if session_id:
                        self.logger.debug(f"   🔑 SID: {session_id}")
                    
                    # ===== ДИАГНОСТИКА: содержимое =====
                    body_len = len(body)
                    question_len = len(question)
                    self.logger.debug(f"   📄 Тело: {body_len} символов, Вопрос: {question_len} символов")
                    
                    if not question or not question.strip():
                        self.logger.warning(f"⚠️ Письмо {email_id_str} содержит пустой вопрос")
                        self.logger.debug(f"   Тело (первые 200 символов): {body[:200]}")
                        
                        # ===== ДИАГНОСТИКА: сохраняем проблемное письмо =====
                        self.save_debug_email(email_id_str, from_addr, subject, body, "empty_question")
                        
                        # Не удаляем письмо, а перемещаем в папку ошибок
                        error_folder = self.config.get('error_folder', 'Errors')
                        try:
                            self.imap.create(error_folder)
                            self.imap.copy(email_id, error_folder)
                            self.imap.store(email_id, '+FLAGS', '\\Seen')
                            self.logger.debug(f"   📁 Письмо перемещено в '{error_folder}'")
                        except Exception as e:
                            self.logger.error(f"   ❌ Ошибка перемещения: {e}")
                        
                        continue
                    
                    # Проверяем фильтры
                    passes, reason = self.passes_filters(subject, from_addr, body)
                    
                    # ===== ДИАГНОСТИКА: результат фильтрации =====
                    self.logger.debug(f"   🔍 Фильтры: {'✅ ПРОШЕЛ' if passes else '❌ НЕ ПРОШЕЛ'} - {reason}")
                    
                    # ===== ДИАГНОСТИКА: сохраняем отфильтрованные письма =====
                    if not passes:
                        filtered_count += 1
                        self.logger.email_processed(from_addr, subject, "FILTERED", reason)
                        
                        # Сохраняем информацию об отфильтрованном письме
                        self.save_debug_email(email_id_str, from_addr, subject, body, f"filtered_{reason[:30]}")
                        
                        # ===== ВАЖНО: НЕ ПОМЕЧАЕМ КАК ПРОЧИТАННОЕ =====
                        # Просто перемещаем в Filtered, но оставляем непрочитанным
                        # Это позволит увидеть их в папке Filtered как непрочитанные
                        
                        filtered_folder = self.config.get('filtered_folder', 'Filtered')
                        try:
                            self.imap.create(filtered_folder)
                            self.imap.copy(email_id, filtered_folder)
                            # НЕ помечаем как прочитанное!
                            # self.imap.store(email_id, '+FLAGS', '\\Seen')  # <-- УБРАТЬ
                            
                            if self.config.get('delete_after_filtering', False):
                                self.imap.store(email_id, '+FLAGS', '\\Deleted')
                            
                            self.logger.debug(f"   📁 Письмо перемещено в '{filtered_folder}' (НЕ прочитано)")
                        except Exception as e:
                            self.logger.error(f"   ❌ Ошибка перемещения: {e}")
                        
                        continue
                    
                    # Письмо прошло фильтры
                    self.logger.email_processed(from_addr, subject, "PROCESSED")
                    question_display = question[:50] + "..." if len(question) > 50 else question
                    self.logger.debug(f"✅ Письмо ПРОШЛО фильтры. Вопрос: '{question_display}'")
                    
                    emails.append({
                        'id': email_id_str,
                        'subject': subject,
                        'from': from_addr,
                        'date': date,
                        'body': body,
                        'question': question,
                        'session_id': session_id,
                        'raw_message': msg
                    })
                    
                    # Помечаем как прочитанное ТОЛЬКО после успешной обработки
                    if self.config.get('mark_as_read', True):
                        self.imap.store(email_id, '+FLAGS', '\\Seen')
                    
                    # ===== ДИАГНОСТИКА: успешно обработано =====
                    self.save_debug_email(email_id_str, from_addr, subject, body, "processed")
                    
                except socket.timeout:
                    self.logger.error(f"⏰ Таймаут при обработке письма {email_id_str}")
                    error_count += 1
                    self.save_debug_email(email_id_str, "unknown", "TIMEOUT", "", "timeout")
                    continue
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"❌ Ошибка обработки письма {email_id_str}: {e}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    
                    # ===== ДИАГНОСТИКА: сохраняем ошибку =====
                    self.save_debug_email(email_id_str, "unknown", f"ERROR: {str(e)[:50]}", "", "error")
                    continue
            
        except socket.timeout:
            self.logger.error("⏰ Таймаут IMAP операции, переподключаюсь...")
            self.disconnect()
            self.connect()
            return []
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения писем: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
        
        # ===== ДИАГНОСТИКА: итоговый отчет =====
        self.logger.info(f"📊 СТАТИСТИКА ОБРАБОТКИ:")
        self.logger.info(f"   Всего писем: {total_count}")
        self.logger.info(f"   Обработано: {len(emails)}")
        self.logger.info(f"   Отфильтровано: {filtered_count}")
        self.logger.info(f"   Ошибок: {error_count}")
        
        # Сохраняем диагностику
        self.save_diagnostics(total_count, len(emails), filtered_count, error_count)
        
        return emails
    
    def move_to_folder(self, email_id: str, folder: str):
        if not self.imap:
            return
        try:
            # Проверяем соединение
            try:
                self.imap.noop()
            except:
                self.logger.warning(f"Соединение потеряно, переподключаюсь...")
                self.connect()
                if not self.imap:
                    return
            
            # Проверяем существование папки
            try:
                self.imap.select(folder)
            except:
                # Папка не существует, создаем
                try:
                    self.imap.create(folder)
                    self.logger.debug(f"📁 Создана папка '{folder}'")
                except Exception as e:
                    self.logger.warning(f"Не удалось создать папку '{folder}': {e}")
                    return
            
            # Копируем письмо
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

    def log_folder_status(self):
        """Логирование статуса всех папок"""
        try:
            # Получаем список всех папок
            status, folders = self.imap.list()
            if status == 'OK':
                self.logger.debug("📁 СТАТУС ПАПОК:")
                for folder in folders:
                    try:
                        # Извлекаем имя папки
                        folder_name = folder.decode().split('"/"')[-1].strip('"')
                        # Пробуем выбрать папку
                        try:
                            select_status = self.imap.select(folder_name)
                            if select_status[0] == 'OK':
                                status, count = self.imap.status(folder_name, '(MESSAGES UNSEEN)')
                                if status == 'OK':
                                    import re
                                    match = re.search(r'MESSAGES\s+(\d+)', count[0].decode())
                                    total = match.group(1) if match else '?'
                                    match_unseen = re.search(r'UNSEEN\s+(\d+)', count[0].decode())
                                    unseen = match_unseen.group(1) if match_unseen else '?'
                                    self.logger.debug(f"   {folder_name}: всего={total}, непрочитанных={unseen}")
                            else:
                                self.logger.debug(f"   {folder_name}: не удалось выбрать")
                        except Exception as e:
                            self.logger.debug(f"   {folder_name}: ошибка - {str(e)[:30]}")
                    except Exception as e:
                        pass
            else:
                self.logger.debug("   ⚠️ Не удалось получить список папок")
        except Exception as e:
            self.logger.debug(f"   ⚠️ Ошибка получения статуса папок: {e}")

    def check_all_emails_count(self):
        """Проверка общего количества писем в INBOX"""
        try:
            status, messages = self.imap.search(None, 'ALL')
            if status == 'OK' and messages[0]:
                total = len(messages[0].split())
                self.logger.debug(f"📊 Всего писем в INBOX: {total}")
                
                # Проверяем прочитанные/непрочитанные
                status, unseen = self.imap.search(None, 'UNSEEN')
                unseen_count = len(unseen[0].split()) if unseen and unseen[0] else 0
                self.logger.debug(f"   Непрочитанных: {unseen_count}")
                self.logger.debug(f"   Прочитанных: {total - unseen_count}")
        except Exception as e:
            self.logger.debug(f"   ⚠️ Ошибка подсчета: {e}")

    def save_debug_email(self, email_id: str, from_addr: str, subject: str, body: str, reason: str):
        """Сохранение письма для диагностики"""
        try:
            debug_dir = Path("logs/debug_emails")
            debug_dir.mkdir(exist_ok=True, parents=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_id = email_id.replace('/', '_')[:20]
            filename = f"{timestamp}_{safe_id}_{reason[:30]}.txt"
            
            with open(debug_dir / filename, 'w', encoding='utf-8') as f:
                f.write(f"Email ID: {email_id}\n")
                f.write(f"From: {from_addr}\n")
                f.write(f"Subject: {subject}\n")
                f.write(f"Reason: {reason}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write("="*70 + "\n")
                f.write("BODY:\n")
                f.write("="*70 + "\n")
                f.write(body[:2000] if body else "(empty)")
                f.write("\n" + "="*70 + "\n")
            
            self.logger.debug(f"   💾 Сохранено в debug_emails/{filename}")
        except Exception as e:
            self.logger.debug(f"   ⚠️ Ошибка сохранения: {e}")

    def save_diagnostics(self, total, processed, filtered, errors):
        """Сохранение диагностики в JSON"""
        try:
            self.diagnostics['last_check'] = datetime.now().isoformat()
            self.diagnostics['total_emails'] = total
            self.diagnostics['processed'] = processed
            self.diagnostics['filtered'] = filtered
            self.diagnostics['errors'] = errors
            
            # Сохраняем в файл
            with open(self.debug_file, 'w', encoding='utf-8') as f:
                json.dump(self.diagnostics, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"💾 Диагностика сохранена в {self.debug_file}")
        except Exception as e:
            self.logger.debug(f"⚠️ Ошибка сохранения диагностики: {e}")            