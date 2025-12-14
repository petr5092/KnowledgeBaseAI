# KnowledgeBaseAI

[![CI](https://github.com/AndrewHakmi/KnowledgeBaseAI/actions/workflows/ci.yml/badge.svg)](https://github.com/AndrewHakmi/KnowledgeBaseAI/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-BUSL--1.1-blue)](#license)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](./backend/README.md)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB)](./frontend/README.md)
[![Graph](https://img.shields.io/badge/graph-Neo4j-4581C3)](https://neo4j.com/)
[![Vector](https://img.shields.io/badge/vector-Qdrant-FF4D4D)](https://qdrant.tech/)

**KnowledgeBaseAI** — это **платформа графа знаний**, которая преобразует разрозненный учебный контент в структурированный, запрашиваемый и объяснимый граф понятий, навыков, методов и пререквизитов.

Платформа предназначена для поддержки:

* адаптивных образовательных траекторий
* планирования учебных программ
* аналитики знаний и контроля качества контента
* построения базы знаний с помощью ИИ

---

## Live

* UI: [https://kb.studyninja.ru](https://kb.studyninja.ru), [https://kb.xteam.pro](https://kb.xteam.pro)
* API: [https://api.kb.studyninja.ru](https://api.kb.studyninja.ru), [https://api.kb.xteam.pro](https://api.kb.xteam.pro)

---

## Почему это важно

Большинство образовательных платформ хранят контент в виде страниц и видео.
**KnowledgeBaseAI** хранит его в виде **графа**:

* пререквизиты становятся явными
* пробелы и несогласованности становятся измеримыми
* учебные маршруты становятся вычислимыми
* объяснения становятся трассируемыми («почему эта тема следующая»)

---

## Что можно построить поверх платформы

* интеграции с LMS (прогресс — внутрь, рекомендации — наружу)
* адаптивные дорожные карты для каждого ученика
* дашборды качества контента (покрытие, изолированные узлы, отсутствующие связи)
* ИИ-ассистенты для методистов и разработчиков учебных программ

---

## Ключевые особенности продукта

* **Stateless-ядро**: прогресс пользователей может храниться во внешней LMS; платформа фокусируется на интеллектуальной работе с графом.
* **Graph-first модель**: предметы → разделы → темы → навыки → методы, с пререквизитами и взвешенными связями.
* **Инструменты администрирования**: генерация/импорт баз знаний, пересчёт весов, валидация снимков графа.
* **Готовность к наблюдаемости**: метрики Prometheus, структурированное логирование.

---

## Быстрый старт (Docker)

```bash
cp .env.example .env.dev
ENV_FILE=.env.dev docker compose --env-file .env.dev up -d --build
```

---

## Документация (техническая)

Этот README ориентирован на продукт и концепцию. Технические детали вынесены в отдельные документы:

* Backend: [`backend/README.md`](./backend/README.md)
* Frontend: [`frontend/README.md`](./frontend/README.md)
* Разработка backend: [`backend/development.md`](./backend/development.md)
* Деплой backend: [`backend/deployment.md`](./backend/deployment.md)
* Разработка frontend: [`frontend/development.md`](./frontend/development.md)
* Деплой frontend: [`frontend/deployment.md`](./frontend/deployment.md)

---

## Краткое техническое резюме

* Backend: FastAPI (Python 3.12)
* Frontend: React + TypeScript + Vite
* Хранилища: Neo4j (граф), Postgres (пользователи/аутентификация), Qdrant (векторы)
* Фоновые задачи: Redis + ARQ
* Edge-инфраструктура: Traefik (TLS + маршрутизация)

---

## Модель безопасности (кратко)

* JWT-аутентификация (`/v1/auth/*`)
* Административные эндпоинты защищены ролевой моделью доступа (`/v1/admin/*`)
* Первый администратор инициализируется через переменные окружения при первом деплое

---

## Roadmap (глобально)

### Phase 1 — Укрепление платформы

* промышленное усиление аутентификации (rate limiting, политика паролей, аудит-логи)
* миграции схемы Postgres
* операционные инструкции (backup/restore, реакция на инциденты)

### Phase 2 — Интеграции и экосистема

* коннекторы LMS (импорт прогресса, экспорт рекомендаций)
* генерация OpenAPI-клиентов и SDK
* вебхуки и события для внешних систем

### Phase 3 — Интеллектуальный слой

* улучшенная оценка качества графа и обнаружение аномалий
* объяснимые рекомендации (трассируемые пути)
* гибридный поиск (граф + векторы) для ассистентов

### Phase 4 — Продуктизация

* поддержка multi-tenant
* административный UI для методистов
* enterprise-варианты развёртывания

---

## Вклад в проект

* Перед началом ознакомьтесь с гайдами по разработке (backend/frontend).
* Используйте feature-ветки и pull request’ы.
* Никогда не коммитьте секреты (production `.env` файлы должны быть в `.gitignore`).

---

## Лицензия

Проект распространяется по лицензии **Business Source License 1.1 (BUSL-1.1)**.

См.: [`LICENSE`](./LICENSE)