#!/usr/bin/env python3
"""
Автоматическая привязка методов к навыкам на основе applicability_types
"""

import json
import psycopg2
from typing import Dict, List, Set, Tuple
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SkillMethodLinker:
    def __init__(self, db_config: Dict[str, str]):
        """
        Инициализация линкера
        
        Args:
            db_config: Конфигурация подключения к БД
        """
        self.db_config = db_config
        self.applicability_types = self._load_applicability_types()
        
    def _load_applicability_types(self) -> Dict[str, Dict]:
        """Загружает словарь типов применимости"""
        try:
            with open('kb/applicability_types.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Файл applicability_types.json не найден, используется пустой словарь")
            return {}
    
    def connect_db(self):
        """Подключение к базе данных"""
        return psycopg2.connect(**self.db_config)
    
    def get_skills_with_types(self, conn) -> List[Tuple[str, List[str]]]:
        """
        Получает навыки с их типами применимости из БД
        
        Returns:
            List of (skill_uid, applicability_types)
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT uid, applicability_types 
            FROM skills 
            WHERE applicability_types IS NOT NULL
        """)
        return cursor.fetchall()
    
    def get_methods_with_types(self, conn) -> List[Tuple[str, List[str]]]:
        """
        Получает методы с их типами применимости из БД
        
        Returns:
            List of (method_uid, applicability_types)
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT uid, applicability_types 
            FROM methods 
            WHERE applicability_types IS NOT NULL
        """)
        return cursor.fetchall()
    
    def calculate_compatibility(self, skill_types: List[str], method_types: List[str]) -> float:
        """
        Вычисляет совместимость между навыком и методом
        
        Args:
            skill_types: Типы применимости навыка
            method_types: Типы применимости метода
            
        Returns:
            Коэффициент совместимости от 0 до 1
        """
        if not skill_types or not method_types:
            return 0.0
        
        skill_set = set(skill_types)
        method_set = set(method_types)
        
        # Прямое пересечение
        intersection = skill_set & method_set
        if intersection:
            # Базовая совместимость по пересечению
            base_score = len(intersection) / len(skill_set | method_set)
            
            # Бонус за точное совпадение ключевых типов
            key_matches = 0
            for skill_type in skill_types:
                if skill_type in method_types:
                    # Проверяем, является ли тип ключевым (основным математическим доменом)
                    if self._is_key_domain(skill_type):
                        key_matches += 1
            
            key_bonus = key_matches * 0.2
            return min(1.0, base_score + key_bonus)
        
        return 0.0
    
    def _is_key_domain(self, type_name: str) -> bool:
        """Проверяет, является ли тип ключевым математическим доменом"""
        key_domains = {
            'algebra', 'geometry', 'trigonometry', 'functions', 
            'probability', 'statistics', 'number_theory', 'analysis',
            'vectors', 'combinatorics', 'arithmetic'
        }
        return type_name in key_domains
    
    def determine_weight(self, compatibility: float) -> str:
        """
        Определяет вес связи на основе совместимости
        
        Args:
            compatibility: Коэффициент совместимости
            
        Returns:
            Вес связи: 'primary', 'secondary', 'auxiliary'
        """
        if compatibility >= 0.8:
            return 'primary'
        elif compatibility >= 0.5:
            return 'secondary'
        else:
            return 'auxiliary'
    
    def link_skills_methods(self, min_compatibility: float = 0.3) -> List[Dict]:
        """
        Создает связи между навыками и методами
        
        Args:
            min_compatibility: Минимальная совместимость для создания связи
            
        Returns:
            Список связей в формате skill_methods.jsonl
        """
        conn = self.connect_db()
        try:
            skills = self.get_skills_with_types(conn)
            methods = self.get_methods_with_types(conn)
            
            links = []
            
            for skill_uid, skill_types in skills:
                skill_links = []
                
                for method_uid, method_types in methods:
                    compatibility = self.calculate_compatibility(skill_types, method_types)
                    
                    if compatibility >= min_compatibility:
                        weight = self.determine_weight(compatibility)
                        
                        link = {
                            'skill_uid': skill_uid,
                            'method_uid': method_uid,
                            'weight': weight,
                            'confidence': round(compatibility, 3)
                        }
                        skill_links.append((compatibility, link))
                
                # Сортируем по совместимости и добавляем лучшие связи
                skill_links.sort(key=lambda x: x[0], reverse=True)
                
                # Ограничиваем количество связей на навык
                max_links_per_skill = 5
                for _, link in skill_links[:max_links_per_skill]:
                    links.append(link)
            
            logger.info(f"Создано {len(links)} автоматических связей")
            return links
            
        finally:
            conn.close()
    
    def save_links_to_db(self, links: List[Dict]):
        """
        Сохраняет связи в базу данных
        
        Args:
            links: Список связей для сохранения
        """
        conn = self.connect_db()
        try:
            cursor = conn.cursor()
            
            # Очищаем существующие автоматические связи
            cursor.execute("DELETE FROM skill_methods WHERE is_auto_generated = true")
            
            # Вставляем новые связи
            for link in links:
                cursor.execute("""
                    INSERT INTO skill_methods (skill_uid, method_uid, weight, confidence, is_auto_generated)
                    VALUES (%s, %s, %s, %s, true)
                    ON CONFLICT (skill_uid, method_uid) DO UPDATE SET
                        weight = EXCLUDED.weight,
                        confidence = EXCLUDED.confidence,
                        is_auto_generated = EXCLUDED.is_auto_generated
                """, (
                    link['skill_uid'],
                    link['method_uid'],
                    link['weight'],
                    link['confidence']
                ))
            
            conn.commit()
            logger.info(f"Сохранено {len(links)} связей в базу данных")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при сохранении связей: {e}")
            raise
        finally:
            conn.close()
    
    def export_links_to_jsonl(self, links: List[Dict], filename: str):
        """
        Экспортирует связи в JSONL файл
        
        Args:
            links: Список связей
            filename: Имя файла для сохранения
        """
        with open(filename, 'w', encoding='utf-8') as f:
            for link in links:
                f.write(json.dumps(link, ensure_ascii=False) + '\n')
        
        logger.info(f"Экспортировано {len(links)} связей в {filename}")


def main():
    """Основная функция для запуска автоматической привязки"""
    
    # Конфигурация подключения к БД
    db_config = {
        'host': 'localhost',
        'database': 'knowledge_base',
        'user': 'kb_user',
        'password': 'kb_password',
        'port': 5432
    }
    
    try:
        linker = SkillMethodLinker(db_config)
        
        # Создаем автоматические связи
        logger.info("Начинаем автоматическую привязку методов к навыкам...")
        links = linker.link_skills_methods(min_compatibility=0.3)
        
        # Сохраняем в БД
        linker.save_links_to_db(links)
        
        # Экспортируем в JSONL
        linker.export_links_to_jsonl(links, 'kb/auto_skill_methods.jsonl')
        
        logger.info("Автоматическая привязка завершена успешно!")
        
        # Статистика
        weights_count = {}
        for link in links:
            weight = link['weight']
            weights_count[weight] = weights_count.get(weight, 0) + 1
        
        logger.info("Статистика по весам связей:")
        for weight, count in weights_count.items():
            logger.info(f"  {weight}: {count}")
            
    except Exception as e:
        logger.error(f"Ошибка при выполнении автоматической привязки: {e}")
        raise


if __name__ == "__main__":
    main()