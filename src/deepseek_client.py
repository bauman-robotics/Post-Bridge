#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для работы с DeepSeek API
Использует conversation_id для сессий
"""

import json
import requests
from typing import List, Dict, Optional, Tuple

class DeepSeekClient:
    """Клиент для DeepSeek API с поддержкой сессий через conversation_id"""
    
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
             conversation_id: Optional[str] = None,
             **kwargs) -> Optional[Dict]:
        """
        Отправка запроса к DeepSeek
        
        Args:
            messages: Список сообщений [{"role": "user", "content": "..."}]
            stream: Использовать потоковый режим
            conversation_id: ID беседы для продолжения диалога (ВАЖНО!)
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
        
        # ВАЖНО: используем conversation_id, а не session_id!
        if conversation_id:
            payload['conversation_id'] = conversation_id
        
        # Добавляем расширенные параметры
        if self.config.get('thinking'):
            payload['thinking'] = True
        if self.config.get('search'):
            payload['search'] = True
        
        print(f"🔍 Отправка запроса к API: {endpoint}")
        print(f"   conversation_id: {conversation_id}")
        print(f"   messages: {len(messages)}")
        
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
    
    def ask_with_context(self, 
                         question: str,
                         context: Optional[str] = None,
                         system_prompt: Optional[str] = None,
                         conversation_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Вопрос с контекстом
        
        Args:
            question: Вопрос пользователя
            context: Дополнительный контекст
            system_prompt: Системный промпт
            conversation_id: ID беседы для продолжения диалога
            
        Returns:
            (Текст ответа, Conversation ID) или (None, None)
        """
        full_question = question
        if context:
            full_question = f"Контекст:\n{context}\n\nВопрос:\n{question}"
        
        return self.ask(full_question, system_prompt, conversation_id)


# Пример использования
if __name__ == "__main__":
    import yaml
    
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    client = DeepSeekClient(config['deepseek'])
    
    # Тест сессии
    conv_id = None
    
    # Первый вопрос
    answer, conv_id = client.ask("Меня зовут Алексей. Я люблю Python.")
    print(f"Ответ 1: {answer[:100]}...")
    print(f"Conversation ID: {conv_id}")
    
    # Второй вопрос (должен помнить)
    answer, conv_id = client.ask("Какое мое любимое хобби?", conversation_id=conv_id)
    print(f"Ответ 2: {answer[:100]}...")
    print(f"Conversation ID: {conv_id}")