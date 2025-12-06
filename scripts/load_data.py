#!/usr/bin/env python3
"""
Скрипт загрузки данных из JSONL файлов в PostgreSQL
"""

import json
import psycopg2
import os
from typing import Dict, List
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, db_config: Dict[str, str]):
        """
        Инициализация загрузчика данных
        
        Args:
            db_config: Конфигурация подключения к БД
        """
        self.db_config = db_config
        self.kb_dir = 'kb'
    
    def connect_db(self):
        """Подключение к базе данных"""
        return psycopg2.connect(**self.db_config)
    
    def load_jsonl_file(self, filename: str) -> List[Dict]:
        """
        Загружает данные из JSONL файла
        
        Args:
            filename: Имя файла в директории kb/
            
        Returns:
            Список словарей с данными
        """
        filepath = os.path.join(self.kb_dir, filename)
        if not os.path.exists(filepath):
            logger.warning(f"Файл {filepath} не найден")
            return []
        
        data = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка JSON в {filepath}:{line_num}: {e}")
        
        logger.info(f"Загружено {len(data)} записей из {filename}")
        return data
    
    def load_subjects(self, conn):
        """Загружает предметы"""
        data = self.load_jsonl_file('subjects.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO subjects (uid, title, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description
            """, (item['uid'], item['title'], item.get('description')))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} предметов")
    
    def load_sections(self, conn):
        """Загружает разделы"""
        data = self.load_jsonl_file('sections.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO sections (uid, subject_uid, title, description, order_index)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    subject_uid = EXCLUDED.subject_uid,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    order_index = EXCLUDED.order_index
            """, (
                item['uid'], 
                item['subject_uid'], 
                item['title'], 
                item.get('description'),
                item.get('order_index', 0)
            ))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} разделов")
    
    def load_topics(self, conn):
        """Загружает темы"""
        data = self.load_jsonl_file('topics.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO topics (uid, section_uid, title, description, 
                                  accuracy_threshold, critical_errors_max, median_time_threshold_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    section_uid = EXCLUDED.section_uid,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    accuracy_threshold = EXCLUDED.accuracy_threshold,
                    critical_errors_max = EXCLUDED.critical_errors_max,
                    median_time_threshold_seconds = EXCLUDED.median_time_threshold_seconds
            """, (
                item['uid'],
                item['section_uid'],
                item['title'],
                item.get('description'),
                item.get('accuracy_threshold', 0.8),
                item.get('critical_errors_max', 2),
                item.get('median_time_threshold_seconds', 300)
            ))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} тем")
    
    def load_skills(self, conn):
        """Загружает навыки"""
        data = self.load_jsonl_file('skills.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO skills (uid, subject_uid, title, definition, applicability_types)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    subject_uid = EXCLUDED.subject_uid,
                    title = EXCLUDED.title,
                    definition = EXCLUDED.definition,
                    applicability_types = EXCLUDED.applicability_types
            """, (
                item['uid'],
                item['subject_uid'],
                item['title'],
                item.get('description'),
                item.get('applicability_types', [])
            ))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} навыков")
    
    def load_methods(self, conn):
        """Загружает методы"""
        data = self.load_jsonl_file('methods.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO methods (uid, title, method_text, applicability_types)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    title = EXCLUDED.title,
                    method_text = EXCLUDED.method_text,
                    applicability_types = EXCLUDED.applicability_types
            """, (
                item['uid'],
                item['title'],
                item['method_text'],
                item.get('applicability_types', [])
            ))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} методов")
    
    def load_examples(self, conn):
        """Загружает примеры"""
        data = self.load_jsonl_file('examples.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO examples (uid, subject_uid, topic_uid, title, statement, difficulty_level)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    subject_uid = EXCLUDED.subject_uid,
                    topic_uid = EXCLUDED.topic_uid,
                    title = EXCLUDED.title,
                    statement = EXCLUDED.statement,
                    difficulty_level = EXCLUDED.difficulty_level
            """, (
                item['uid'],
                item['subject_uid'],
                item.get('topic_uid'),
                item['title'],
                item['statement'],
                item.get('difficulty_level', 'medium')
            ))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} примеров")
    
    def load_errors(self, conn):
        """Загружает ошибки"""
        data = self.load_jsonl_file('errors.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO errors (uid, title, description, error_type)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    error_type = EXCLUDED.error_type
            """, (
                item['uid'],
                item['title'],
                item.get('description') or item.get('error_text'),
                item.get('error_type', 'conceptual')
            ))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} ошибок")
    
    def load_skill_methods(self, conn):
        """Загружает связи навыков и методов"""
        data = self.load_jsonl_file('skill_methods.jsonl')
        if not data:
            return
        
        cursor = conn.cursor()
        for item in data:
            cursor.execute("""
                INSERT INTO skill_methods (skill_uid, method_uid, weight, confidence, is_auto_generated)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (skill_uid, method_uid) DO UPDATE SET
                    weight = EXCLUDED.weight,
                    confidence = EXCLUDED.confidence,
                    is_auto_generated = EXCLUDED.is_auto_generated,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                item['skill_uid'],
                item['method_uid'],
                item.get('weight', 'secondary'),
                item.get('confidence', 0.5),
                item.get('is_auto_generated', False)
            ))
        
        conn.commit()
        logger.info(f"Загружено {len(data)} связей навыков и методов")
    
    def load_all_data(self):
        """Загружает все данные в правильном порядке"""
        conn = self.connect_db()
        try:
            logger.info("Начинаем загрузку данных...")
            
            # Загружаем в порядке зависимостей
            self.load_subjects(conn)
            self.load_sections(conn)
            self.load_topics(conn)
            self.load_skills(conn)
            self.load_methods(conn)
            self.load_examples(conn)
            self.load_errors(conn)
            self.load_skill_methods(conn)
            
            logger.info("Загрузка данных завершена успешно!")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при загрузке данных: {e}")
            raise
        finally:
            conn.close()


def main():
    """Основная функция"""
    
    # Конфигурация подключения к БД
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'knowledge_base'),
        'user': os.getenv('DB_USER', 'kb_user'),
        'password': os.getenv('DB_PASSWORD', 'kb_password'),
        'port': int(os.getenv('DB_PORT', '5432')),
    }
    
    try:
        loader = DataLoader(db_config)
        loader.load_all_data()
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        exit(1)


if __name__ == "__main__":
    main()