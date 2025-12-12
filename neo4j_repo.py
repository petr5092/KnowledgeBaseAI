import os
import time
from typing import Callable, Any, Dict, List, Optional
from neo4j import GraphDatabase

# NOTE: User-related relations are deprecated.
# KnowledgeBaseAI core no longer stores any user data inside Neo4j.


class Neo4jRepo:
    """Адаптер-репозиторий для работы с Neo4j.

    Обеспечивает:
    - Подключение к Neo4j из ENV
    - Надёжные read/write с ретраями
    - UNWIND-загрузку батчами
    - Утилиты для пользователей и их весов
    """
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, max_retries: int = 3, backoff_sec: float = 0.8):
        self.uri = uri or os.getenv('NEO4J_URI')
        self.user = user or os.getenv('NEO4J_USER')
        self.password = password or os.getenv('NEO4J_PASSWORD')
        if not self.uri or not self.user or not self.password:
            raise RuntimeError('Missing Neo4j connection environment variables')
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.max_retries = max_retries
        self.backoff_sec = backoff_sec

    def close(self):
        self.driver.close()

    def _retry(self, fn: Callable[[Any], Any]) -> Any:
        """Повторить операцию с экспоненциальной задержкой при временных сбоях."""
        attempt = 0
        last_exc = None
        while attempt < self.max_retries:
            try:
                with self.driver.session() as session:
                    return fn(session)
            except Exception as e:
                last_exc = e
                attempt += 1
                time.sleep(self.backoff_sec * attempt)
        raise last_exc

    def write(self, query: str, params: Dict | None = None) -> None:
        """Выполнить записывающий Cypher-запрос."""
        def _fn(session):
            session.execute_write(lambda tx: tx.run(query, **(params or {})))
        return self._retry(_fn)

    def read(self, query: str, params: Dict | None = None) -> List[Dict]:
        """Выполнить читающий Cypher-запрос и вернуть список словарей."""
        def _fn(session):
            def reader(tx):
                res = tx.run(query, **(params or {}))
                return [dict(r) for r in res]
            return session.execute_read(reader)
        return self._retry(_fn)

    def _chunks(self, rows: List[Dict], size: int) -> List[List[Dict]]:
        return [rows[i:i+size] for i in range(0, len(rows), size)]

    def write_unwind(self, query: str, rows: List[Dict], chunk_size: int = 500) -> None:
        """Загрузить данные батчами через UNWIND-параметр rows."""
        if not rows:
            return
        for chunk in self._chunks(rows, chunk_size):
            def _fn(session):
                session.execute_write(lambda tx: tx.run(query, rows=chunk))
            self._retry(_fn)

    # NOTE: User-related relations are deprecated.
    # KnowledgeBaseAI core no longer stores any user data inside Neo4j.

    # Convenience helpers
    def ensure_user(self, user_id: str) -> None:
        """Гарантировать наличие узла User."""
        self.write("MERGE (:User {id:$id})", {"id": user_id})

    def set_topic_user_weight(self, user_id: str, topic_uid: str, weight: float) -> None:
        """Установить персональный вес пользователя по теме."""
        self.ensure_user(user_id)
        self.write(
            "MATCH (u:User {id:$uid}), (t:Topic {uid:$tuid}) MERGE (u)-[r:PROGRESS_TOPIC]->(t) SET r.dynamic_weight=$dw",
            {"uid": user_id, "tuid": topic_uid, "dw": weight}
        )

    def get_topic_user_weight(self, user_id: str, topic_uid: str) -> Dict | None:
        """Получить персональный вес пользователя по теме."""
        rows = self.read(
            "MATCH (:User {id:$uid})-[r:PROGRESS_TOPIC]->(t:Topic {uid:$tuid}) RETURN r.dynamic_weight AS dw, t.static_weight AS sw, t.title AS title",
            {"uid": user_id, "tuid": topic_uid}
        )
        return rows[0] if rows else None

    def set_skill_user_weight(self, user_id: str, skill_uid: str, weight: float) -> None:
        """Установить персональный вес пользователя по навыку."""
        self.ensure_user(user_id)
        self.write(
            "MATCH (u:User {id:$uid}), (s:Skill {uid:$suid}) MERGE (u)-[r:PROGRESS_SKILL]->(s) SET r.dynamic_weight=$dw",
            {"uid": user_id, "suid": skill_uid, "dw": weight}
        )

    def get_skill_user_weight(self, user_id: str, skill_uid: str) -> Dict | None:
        """Получить персональный вес пользователя по навыку."""
        rows = self.read(
            "MATCH (:User {id:$uid})-[r:PROGRESS_SKILL]->(s:Skill {uid:$suid}) RETURN r.dynamic_weight AS dw, s.static_weight AS sw, s.title AS title",
            {"uid": user_id, "suid": skill_uid}
        )
        return rows[0] if rows else None
