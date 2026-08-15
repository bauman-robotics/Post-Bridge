#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для работы с DeepSeek API
Независимый клиент для отправки запросов
"""

import json
import requests
from typing import List, Dict, Optional, Generator

class DeepSeekClient:
    """Клиент для DeepSeek API"""
    
    def __init__(self, config: Dict):
        """
        Инициализация клиента
        
        Args:
            config: Словарь с конфигурацией DeepSeek
        """
        self.config = config
        self.base_url = config.get('api_url', 'http://localhost:8000').rstrip('/')
        self.session = requests.Session()
        
    def chat(self, 
             messages: List[Dict[str, str]], 
             stream: bool = False,
             **kwargs) -> Optional[Dict]:
        """
        Отправка запроса к DeepSeek
        
        Args:
            messages: Список сообщений [{"role": "user", "content": "..."}]
            stream: Использовать потоковый режим
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ от API или None
        """
        endpoint = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": self.config.get('model', 'deepseek-chat'),
            "messages": messages,
            "temperature": self.config.get('temperature', 0.7),
            "max_tokens": self.config.get('max_tokens', 2000),
            "stream": stream,
            **kwargs
        }
        
        # Добавляем расширенные параметры
        if self.config.get('thinking'):
            payload['thinking'] = True
        if self.config.get('search'):
            payload['search'] = True
        
        try:
            response = self.session.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.config.get('timeout', 60)
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка DeepSeek API: {e}")
            return None
    
    def ask(self, 
            question: str, 
            system_prompt: Optional[str] = None,
            **kwargs) -> Optional[str]:
        """
        Упрощенный метод для одного вопроса
        
        Args:
            question: Текст вопроса
            system_prompt: Системный промпт
            **kwargs: Дополнительные параметры
            
        Returns:
            Текст ответа или None
        """
        messages = []
        
        if system_prompt or self.config.get('system_prompt'):
            messages.append({
                "role": "system",
                "content": system_prompt or self.config.get('system_prompt')
            })
        
        messages.append({"role": "user", "content": question})
        
        response = self.chat(messages, **kwargs)
        
        if response and 'choices' in response and response['choices']:
            return response['choices'][0]['message']['content']
        
        return None
    
    def ask_with_context(self, 
                         question: str,
                         context: Optional[str] = None,
                         system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Вопрос с контекстом
        
        Args:
            question: Вопрос пользователя
            context: Дополнительный контекст
            system_prompt: Системный промпт
            
        Returns:
            Текст ответа
        """
        full_question = question
        if context:
            full_question = f"Контекст:\n{context}\n\nВопрос:\n{question}"
        
        return self.ask(full_question, system_prompt)


# Пример использования
if __name__ == "__main__":
    # Тестирование клиента
    import yaml
    
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    client = DeepSeekClient(config['deepseek'])
    
    # Простой вопрос
    answer = client.ask("Привет! Как дела?")
    print(f"Ответ: {answer}")
    
    # Вопрос с контекстом
    answer = client.ask_with_context(
        "Что это за проект?",
        context="Это скрипт для интеграции DeepSeek с почтой."
    )
    print(f"Ответ с контекстом: {answer}")