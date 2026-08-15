#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для логирования
Создает единый лог-файл для всех операций
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

class Logger:
    """Класс для логирования в файл и консоль"""
    
    def __init__(self, log_dir: str = "logs", log_file: str = None):
        """
        Инициализация логгера
        
        Args:
            log_dir: Папка для логов
            log_file: Имя файла лога (если None - генерируется автоматически)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # Создаем имя файла если не указано
        if log_file is None:
            timestamp = datetime.now().strftime('%Y%m%d')
            self.log_file = self.log_dir / f"deepseek_bridge_{timestamp}.log"
        else:
            self.log_file = self.log_dir / log_file
        
        # Создаем файл лога если его нет
        self.log_file.touch(exist_ok=True)
        
        # Для цветного вывода в консоль
        self.colors = {
            'INFO': '\033[92m',    # Зеленый
            'WARNING': '\033[93m',  # Желтый
            'ERROR': '\033[91m',    # Красный
            'DEBUG': '\033[94m',    # Синий
            'FILTER': '\033[96m',   # Голубой
            'RESET': '\033[0m'      # Сброс
        }
    
    def _write(self, level: str, message: str, to_console: bool = True):
        """Запись сообщения в лог и консоль"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level}] {message}"
        
        # Запись в файл
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
        except Exception as e:
            print(f"⚠️  Ошибка записи в лог: {e}")
        
        # Вывод в консоль с цветом
        if to_console:
            color = self.colors.get(level, self.colors['RESET'])
            print(f"{color}{log_line}{self.colors['RESET']}")
    
    def info(self, message: str, to_console: bool = True):
        """Логирование информационного сообщения"""
        self._write('INFO', message, to_console)
    
    def warning(self, message: str, to_console: bool = True):
        """Логирование предупреждения"""
        self._write('WARNING', message, to_console)
    
    def error(self, message: str, to_console: bool = True):
        """Логирование ошибки"""
        self._write('ERROR', message, to_console)
    
    def debug(self, message: str, to_console: bool = True):
        """Логирование отладочного сообщения"""
        self._write('DEBUG', message, to_console)
    
    def filter_info(self, message: str, to_console: bool = True):
        """Логирование информации о фильтрации"""
        self._write('FILTER', message, to_console)
    
    def email_processed(self, from_addr: str, subject: str, status: str, reason: str = ""):
        """Специальный метод для логирования обработки писем"""
        message = f"Email from {from_addr} | Subject: {subject} | Status: {status}"
        if reason:
            message += f" | Reason: {reason}"
        
        if status == "FILTERED":
            self.filter_info(message)
        elif status == "ERROR":
            self.error(message)
        elif status == "PROCESSED":
            self.info(message)
        else:
            self.debug(message)

# Глобальный экземпляр логгера
logger = None

def get_logger(log_dir: str = "logs", log_file: str = None) -> Logger:
    """Получение глобального экземпляра логгера"""
    global logger
    if logger is None:
        logger = Logger(log_dir, log_file)
    return logger