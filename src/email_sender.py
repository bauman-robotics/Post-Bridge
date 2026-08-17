#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для отправки почты
Отправляет ответы на письма
"""

import smtplib
import re
from email.message import EmailMessage
from email.header import Header
from email.utils import formataddr
from typing import Dict, Optional
from datetime import datetime

class EmailSender:
    """Класс для отправки писем"""
    
    def __init__(self, config: Dict):
        """
        Инициализация отправителя
        
        Args:
            config: Словарь с настройками почты
        """
        self.config = config
        self.smtp = None
        
        # Загружаем настройки из конфига
        self.include_question = config.get('include_question_in_response', True)
        self.signature = config.get('response_signature', "🤖 Это автоматический ответ от DeepSeek AI.")
        self.footer = config.get('response_footer', "")
        self.include_session_in_subject = config.get('include_session_in_subject', True)
    
    def connect(self) -> bool:
        """Подключение к SMTP серверу"""
        try:
            smtp_port = self.config.get('smtp_port', 465)
            self.smtp = smtplib.SMTP_SSL(
                self.config['smtp_server'],
                smtp_port
            )
            self.smtp.login(self.config['username'], self.config['password'])
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к SMTP: {e}")
            return False
    
    def disconnect(self):
        """Отключение от сервера"""
        if self.smtp:
            try:
                self.smtp.quit()
            except:
                pass
            self.smtp = None
    
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
        
    def send_error_response(self,
                           to_email: str,
                           error_msg: str,
                           original_question: str = "",
                           original_subject: str = "",
                           session_id: Optional[str] = None) -> bool:
        """
        Отправка письма об ошибке
        
        Args:
            to_email: Email получателя
            error_msg: Сообщение об ошибке
            original_question: Оригинальный вопрос
            original_subject: Оригинальная тема письма
            session_id: ID сессии
            
        Returns:
            True если отправлено успешно
        """
        if not self.smtp and not self.connect():
            return False
        
        try:
            msg = EmailMessage()
            
            # Тема с session_id
            if self.include_session_in_subject and session_id:
                session_tag = f"[SID:{session_id}]"
                if original_subject:
                    subject = f"{session_tag} Re: {original_subject}"
                else:
                    subject = f"{session_tag} Ошибка обработки запроса"
            else:
                if original_subject:
                    subject = f"Re: {original_subject}"
                else:
                    subject = "Ошибка обработки запроса"
            
            msg['Subject'] = subject
            msg['From'] = self.config['username']
            msg['To'] = to_email
            
            body_parts = []
            
            # Приветствие
            greeting = self.config.get('greeting', "Здравствуйте!")
            body_parts.append(greeting)
            body_parts.append("")
            
            body_parts.append("К сожалению, не удалось обработать ваш запрос.")
            body_parts.append("")
            
            # Добавляем вопрос если нужно и если есть
            if original_question and self.include_question:
                body_parts.append("📝 **Ваш вопрос:**")
                body_parts.append(original_question)
                body_parts.append("")
            
            body_parts.append("❌ **Ошибка:**")
            body_parts.append(error_msg)
            body_parts.append("")
            body_parts.append("Пожалуйста, попробуйте позже или уточните ваш вопрос.")
            body_parts.append("")
            body_parts.append("---")
            if self.signature:
                body_parts.append(self.signature)
            body_parts.append(f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            
            body = '\n'.join(body_parts)
            msg.set_content(body, charset='utf-8')
            
            self.smtp.send_message(msg)
            print(f"✅ Отправлено письмо об ошибке на {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки письма об ошибке: {e}")
            return False
    
    def send_plain_text(self,
                        to_email: str,
                        subject: str,
                        body: str) -> bool:
        """
        Отправка простого текстового письма
        
        Args:
            to_email: Email получателя
            subject: Тема письма
            body: Текст письма
            
        Returns:
            True если отправлено успешно
        """
        if not self.smtp and not self.connect():
            return False
        
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.config['username']
            msg['To'] = to_email
            msg.set_content(body, charset='utf-8')
            
            self.smtp.send_message(msg)
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки письма: {e}")
            return False


# Пример использования
if __name__ == "__main__":
    import yaml
    
    # Загружаем конфиг
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    sender = EmailSender(config['email'])
    
    if sender.connect():
        # Отправка тестового письма с вопросом и сессией
        sender.send_response(
            to_email="recipient@example.com",
            question="Какая погода будет завтра в Москве?",
            answer="Завтра в Москве ожидается переменная облачность, температура +20°C, без осадков.",
            original_subject="Вопрос о погоде",
            session_id="abc12345",
            is_new_session=True
        )
        sender.disconnect()