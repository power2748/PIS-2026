# Лекция 15. Основы DevOps: культура, контейнеризация, оркестрация, GitOps

> **Дисциплина:** Проектирование интернет-систем (ПИС)
> **Курс:** 3, Семестр: 6
> **Тема по учебной программе:** Тема 15 - Основы DevOps
> **ADR-диапазон:** ADR-029 - ADR-030

---

## Результаты обучения

После лекции студент сможет:

1. Определить **DevOps** как культуру и набор практик.
2. Объяснить роль **контейнеризации** (Docker) и **оркестрации** (Kubernetes, обзор).
3. Написать `Dockerfile` и `docker-compose.yml` для микросервисов.
4. Описать экосистему инструментов DevOps.
5. Объяснить принципы **GitOps** (обзор): инфраструктура как код в Git.

---

## Пререквизиты

- Микросервисная архитектура из **лекции 11** (dispatch, operations, resources).
- docker-compose с Traefik из **лекции 11**.
- Межпроцессное взаимодействие из **лекции 12** (REST, gRPC, RabbitMQ).

---

## 1. Введение: что такое DevOps

### Проблема: «стена между Dev и Ops»

Традиционно разработчики (Dev) пишут код и «перебрасывают» его операционной команде (Ops) для развёртывания. Результат:

- Dev: «У меня работает!»
- Ops: «На проде не работает!»
- Оба: ищут виноватого.

### DevOps - определение

> **[О8] Дэниелс, Дэвис:** «DevOps - это культура, практики и инструменты, которые повышают способность организации быстро и надёжно доставлять приложения и сервисы.»

DevOps - это **не должность, не инструмент и не команда**. Это:

1. **Культура** - общая ответственность за весь жизненный цикл (Dev + Ops + QA).
2. **Практики** - CI/CD, IaC, мониторинг, автоматизация.
3. **Инструменты** - Docker, Kubernetes, GitHub Actions, Terraform, Prometheus.

### История DevOps (кратко)

| Год | Событие |
| --- | ------- |
| 2008 | Patrick Debois, Andrew Shafer - первые идеи на Agile Conference |
| 2009 | Первый DevOpsDays (Гент, Бельгия) |
| 2010 | Jez Humble - «Continuous Delivery» |
| 2013 | Docker 0.1 - контейнеризация как стандарт |
| 2014 | Kubernetes 1.0 - оркестрация контейнеров |
| 2017 | GitOps (Weaveworks) - декларативная инфраструктура через Git |

---

## 2. Основные понятия и терминология

**Определения:**

- **CI (Continuous Integration)** - автоматическая сборка и тестирование при каждом коммите.
- **CD (Continuous Delivery)** - автоматическая доставка до staging; деплой на production - ручной (одна кнопка).
- **CD (Continuous Deployment)** - полностью автоматический деплой на production.
- **IaC (Infrastructure as Code)** - описание инфраструктуры в коде (Terraform, Ansible, Pulumi).
- **GitOps** - IaC + Git как единый источник правды + автоматическая синхронизация.
- **Контейнер** - изолированный процесс с собственной файловой системой, сетью и ресурсами.
- **Образ (Image)** - неизменяемый шаблон для создания контейнеров.
- **Оркестрация** - автоматическое управление множеством контейнеров (запуск, масштабирование, восстановление).

---

## 3. Контейнеризация: Docker

### Зачем контейнеры

| Проблема | Решение Docker |
| -------- | -------------- |
| «У меня работает» | Образ = код + зависимости + ОС → одинаково везде |
| Конфликт зависимостей | Каждый сервис - свой контейнер |
| Долгая настройка окружения | `docker-compose up` за секунды |
| Масштабирование | Запуск N копий контейнера |

### Dockerfile для dispatch-service

```dockerfile
# dispatch-service/Dockerfile

# --- Стадия 1: сборка зависимостей ---
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Стадия 2: финальный образ ---
FROM python:3.12-slim

# Непривилегированный пользователь (безопасность)
RUN useradd --create-home appuser
USER appuser

WORKDIR /app

# Копируем зависимости из builder
COPY --from=builder /install /usr/local

# Копируем код приложения
COPY --chown=appuser:appuser . .

# Переменные окружения по умолчанию
ENV PORT=8001
ENV DATABASE_URL="postgresql://dispatch:secret@db:5432/dispatch"

EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:${PORT}/health')"

# Запуск
CMD ["uvicorn", "dispatch.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Пояснение к Dockerfile:**

- **Multi-stage build** - уменьшает размер финального образа (не включает pip, компиляторы).
- **Непривилегированный пользователь** - контейнер не запускается от root.
- **HEALTHCHECK** - Docker/Kubernetes проверяет, жив ли сервис.
- **ENV** - конфигурация через переменные окружения (12-Factor App).

### docker-compose.yml для ПСО «Юго-Запад»

```yaml
# docker-compose.yml - полная инфраструктура ПСО

services:
  # --- API Gateway ---
  traefik:
    image: traefik:v3.0
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8080:8080"  # Dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  # --- Сервисы ---
  dispatch-service:
    build: ./dispatch-service
    environment:
      DATABASE_URL: "postgresql://dispatch:secret@dispatch-db:5432/dispatch"
      RABBITMQ_URL: "amqp://guest:guest@rabbitmq:5672/"
    labels:
      - "traefik.http.routers.dispatch.rule=PathPrefix(`/api/v1/requests`)"
    depends_on:
      dispatch-db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  operations-service:
    build: ./operations-service
    environment:
      DATABASE_URL: "postgresql://operations:secret@operations-db:5432/operations"
      RABBITMQ_URL: "amqp://guest:guest@rabbitmq:5672/"
    labels:
      - "traefik.http.routers.operations.rule=PathPrefix(`/api/v1/operations`)"
    depends_on:
      operations-db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  resources-service:
    build: ./resources-service
    environment:
      DATABASE_URL: "postgresql://resources:secret@resources-db:5432/resources"
      RABBITMQ_URL: "amqp://guest:guest@rabbitmq:5672/"
    labels:
      - "traefik.http.routers.resources.rule=PathPrefix(`/api/v1/resources`)"
    depends_on:
      resources-db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  # --- Базы данных (Database per Service) ---
  dispatch-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: dispatch
      POSTGRES_USER: dispatch
      POSTGRES_PASSWORD: secret
    volumes:
      - dispatch-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dispatch"]
      interval: 10s
      timeout: 5s

  operations-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: operations
      POSTGRES_USER: operations
      POSTGRES_PASSWORD: secret
    volumes:
      - operations-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U operations"]
      interval: 10s
      timeout: 5s

  resources-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: resources
      POSTGRES_USER: resources
      POSTGRES_PASSWORD: secret
    volumes:
      - resources-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U resources"]
      interval: 10s
      timeout: 5s

  # --- Message Broker ---
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    ports:
      - "15672:15672"  # Management UI
    healthcheck:
      test: ["CMD-SHELL", "rabbitmq-diagnostics -q ping"]
      interval: 10s
      timeout: 5s

volumes:
  dispatch-data:
  operations-data:
  resources-data:
```

**Пояснение к docker-compose:**

- **Database per Service** (ADR-021): три отдельных PostgreSQL.
- **Healthcheck** - не запускать сервис, пока БД и RabbitMQ не готовы (`condition: service_healthy`).
- **Traefik labels** - маршрутизация по PathPrefix (API Gateway, лекция 11).
- **Volumes** - данные БД переживают рестарт контейнера.

---

## 4. Оркестрация: Kubernetes (обзор)

### Зачем Kubernetes

Docker Compose - для локальной разработки. В production нужны:

- **Автоматическое масштабирование** (Horizontal Pod Autoscaler).
- **Самовосстановление** (restart при падении).
- **Rolling updates** (обновление без downtime).
- **Service discovery** (DNS внутри кластера).
- **Секреты и конфигурации** (ConfigMap, Secret).

### Основные абстракции

| Абстракция | Назначение | Аналог Docker |
| ---------- | ---------- | ------------- |
| **Pod** | Минимальная единица запуска (1+ контейнер) | Container |
| **Deployment** | Управление репликами Pod | - |
| **Service** | Стабильный endpoint для Pods | Docker network + DNS |
| **Ingress** | Маршрутизация HTTP-трафика | Traefik labels |
| **ConfigMap** | Конфигурация (некритичная) | Environment variables |
| **Secret** | Конфигурация (чувствительная) | - |
| **Namespace** | Изоляция ресурсов | - |

### Пример: Deployment для dispatch-service

```yaml
# k8s/dispatch-deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: dispatch-service
  labels:
    app: dispatch
spec:
  replicas: 2
  selector:
    matchLabels:
      app: dispatch
  template:
    metadata:
      labels:
        app: dispatch
    spec:
      containers:
        - name: dispatch
          image: pso-registry/dispatch-service:1.0.0
          ports:
            - containerPort: 8001
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: dispatch-secrets
                  key: database-url
            - name: RABBITMQ_URL
              valueFrom:
                secretKeyRef:
                  name: dispatch-secrets
                  key: rabbitmq-url
          readinessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
```

```yaml
# k8s/dispatch-service.yaml

apiVersion: v1
kind: Service
metadata:
  name: dispatch-service
spec:
  selector:
    app: dispatch
  ports:
    - port: 80
      targetPort: 8001
  type: ClusterIP
```

**Пояснение к K8s:**

- `replicas: 2` - два экземпляра dispatch (отказоустойчивость).
- `readinessProbe` / `livenessProbe` - Kubernetes проверяет здоровье пода.
- `secretKeyRef` - пароли не в коде, а в Kubernetes Secrets.
- `resources` - ограничения CPU/RAM (не даём сервису «съесть» весь кластер).

---

## 5. Экосистема инструментов DevOps

```mermaid
graph TD
    subgraph "Код"
        Git["Git + GitHub/GitLab"]
    end

    subgraph "CI/CD"
        CI["GitHub Actions / GitLab CI"]
    end

    subgraph "Артефакты"
        REG["Docker Registry<br/>(Harbor, GHCR)"]
    end

    subgraph "Инфраструктура"
        IAC["Terraform / Pulumi"]
        K8S["Kubernetes"]
        DOCKER["Docker"]
    end

    subgraph "Наблюдаемость"
        PROM["Prometheus"]
        GRAF["Grafana"]
        OTEL["OpenTelemetry"]
    end

    subgraph "Секреты"
        VAULT["HashiCorp Vault"]
    end

    Git -->|"push"| CI
    CI -->|"build & test"| REG
    CI -->|"deploy"| K8S
    IAC -->|"provision"| K8S
    K8S -->|"run"| DOCKER
    K8S -->|"metrics"| PROM
    PROM -->|"dashboards"| GRAF
    K8S -->|"traces"| OTEL
    VAULT -->|"inject secrets"| K8S
```

| Категория | Инструменты | Для чего |
| --------- | ----------- | -------- |
| **Version Control** | Git, GitHub, GitLab | Код и IaC |
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins | Сборка, тесты, деплой |
| **Контейнеры** | Docker, Podman | Упаковка приложений |
| **Оркестрация** | Kubernetes, Docker Swarm | Управление контейнерами |
| **IaC** | Terraform, Pulumi, Ansible | Описание инфраструктуры |
| **Registry** | Docker Hub, GHCR, Harbor | Хранение образов |
| **Мониторинг** | Prometheus, Grafana, Datadog | Метрики и дашборды |
| **Трассировка** | OpenTelemetry, Jaeger | Распределённые трейсы |
| **Логи** | ELK Stack, Loki | Агрегация логов |
| **Секреты** | Vault, Sealed Secrets | Безопасное хранение |

---

## 6. GitOps: инфраструктура как код через Git

### Принцип

**GitOps** - подход, при котором:

1. **Git - единый источник правды** для кода И инфраструктуры.
2. Изменения - через **Pull Request** (code review вместо SSH на сервер).
3. **Автоматическая синхронизация** - агент (ArgoCD/Flux) сравнивает Git и кластер, применяет разницу.

### Пример: ПСО «Юго-Запад» - структура GitOps-репозитория

```text
pso-infrastructure/
├── apps/
│   ├── dispatch/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── kustomization.yaml
│   ├── operations/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── kustomization.yaml
│   └── resources/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── kustomization.yaml
├── base/
│   ├── namespace.yaml
│   ├── ingress.yaml
│   └── rabbitmq/
│       └── deployment.yaml
└── overlays/
    ├── staging/
    │   └── kustomization.yaml
    └── production/
        └── kustomization.yaml
```

**Поток GitOps:**

1. Разработчик меняет `deployment.yaml` (например, `image: dispatch:1.1.0`).
2. Создаёт Pull Request → code review → merge в `main`.
3. ArgoCD (агент в кластере) видит разницу Git vs кластер.
4. ArgoCD применяет изменения → rolling update dispatch-service.

```python
# scripts/update_image_tag.py - вспомогательный скрипт для CI/CD

"""Обновляет тег образа в YAML-файле (для GitOps пайплайна)."""

import re
import sys

def update_image_tag(file_path: str, new_tag: str) -> None:
    with open(file_path, "r") as f:
        content = f.read()

    # Заменяем тег образа
    updated = re.sub(
        r"(image:\s*pso-registry/dispatch-service:)\S+",
        rf"\g<1>{new_tag}",
        content,
    )

    with open(file_path, "w") as f:
        f.write(updated)

    print(f"Updated {file_path} → tag: {new_tag}")

if __name__ == "__main__":
    update_image_tag(sys.argv[1], sys.argv[2])
```

---

## 7. Health Checks: готовность и жизнеспособность

### Виды проверок

| Проверка | Вопрос | Что происходит при неудаче |
| -------- | ------ | -------------------------- |
| **Liveness** | «Жив ли процесс?» | Kubernetes убивает и перезапускает Pod |
| **Readiness** | «Готов ли принимать трафик?» | Pod убирается из Service (перестаёт получать запросы) |
| **Startup** | «Успел ли запуститься?» | Liveness/Readiness не проверяются, пока не пройдёт startup |

### Пример: Health endpoint для dispatch-service

```python
# dispatch-service/api/health.py

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
def health_check():
    """Liveness probe: сервис жив."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@router.get("/ready")
def readiness_check(db_pool=None):
    """Readiness probe: сервис готов принимать запросы."""
    # Проверяем подключение к БД
    try:
        if db_pool:
            with db_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}, 503
```

---

## 8. ADR: закрепляем решения

### ADR-029: Docker + docker-compose для локальной разработки

| Поле | Значение |
| ---- | -------- |
| **Контекст** | Три микросервиса + 3 БД + RabbitMQ + Traefik. Локальный запуск без Docker требует 8+ процессов с ручной настройкой. |
| **Решение** | Multi-stage Dockerfile для каждого сервиса. docker-compose.yml для полной инфраструктуры. Healthchecks + depends_on. |
| **Альтернативы** | (a) Vagrant - тяжелее, VM вместо контейнеров. (b) Nix - мощнее, но выше порог входа. (c) Ручная установка - не воспроизводимо. |
| **Затрагиваемые характеристики** | Воспроизводимость ↑, Onboarding ↑ (новый разработчик за 10 мин), Консистентность dev/prod ↑ |
| **Последствия** | Docker обязателен для всех разработчиков. Образы нужно оптимизировать (multi-stage). Секреты не хранить в docker-compose (только для dev). |
| **Проверка** | `docker-compose up` → все сервисы healthy за 60 сек. CI: docker build без ошибок. |

### ADR-030: Kubernetes для production (целевая платформа)

| Поле | Значение |
| ---- | -------- |
| **Контекст** | Production требует: автомасштабирование, rolling updates, self-healing, secret management, resource limits. Docker Compose не обеспечивает. |
| **Решение** | Kubernetes как целевая платформа. Deployment + Service + Ingress. Probes (liveness/readiness). Secrets для credentials. GitOps (ArgoCD) для деплоя. |
| **Альтернативы** | (a) Docker Swarm - проще, но менее функционален. (b) Nomad - альтернатива, меньше экосистема. (c) PaaS (Heroku, Railway) - дороже, меньше контроля. |
| **Затрагиваемые характеристики** | Масштабируемость ↑, Отказоустойчивость ↑, Управляемость ↑, Операционная сложность ↑ |
| **Последствия** | Нужны навыки K8s в команде. Кластер требует обслуживания (или managed K8s: EKS, GKE, AKS). Мониторинг обязателен. |
| **Проверка** | Rolling update без downtime. Pod restarts < 1/час. HPA реагирует на нагрузку. |

---

## Типичные ошибки и антипаттерны

| № | Ошибка | Как исправить |
| - | ------ | ------------- |
| 1 | Контейнер от root | `USER appuser` в Dockerfile |
| 2 | Нет healthcheck | livenessProbe + readinessProbe |
| 3 | Секреты в docker-compose.yml (prod) | Kubernetes Secrets / Vault |
| 4 | Огромный образ (1+ ГБ) | Multi-stage build, slim base |
| 5 | Нет resource limits (Pod «съедает» кластер) | requests + limits в Deployment |
| 6 | SSH на сервер для деплоя | GitOps (ArgoCD/Flux) |
| 7 | Нет volumes для БД (данные теряются) | Persistent volumes |
| 8 | Монолитный docker-compose (один файл для всего) | Разделить по сервисам + override |

---

## Вопросы для самопроверки

1. Что такое DevOps? Почему это культура, а не должность?
2. Чем CI отличается от CD (Delivery) и CD (Deployment)?
3. Что такое IaC? Приведите примеры инструментов.
4. Зачем нужен multi-stage build в Dockerfile?
5. Почему контейнер не должен запускаться от root?
6. Что такое healthcheck? Чем liveness отличается от readiness?
7. Зачем нужен `depends_on: condition: service_healthy`?
8. Что такое Kubernetes Pod? Чем он отличается от Docker-контейнера?
9. Зачем нужны resource requests и limits в Kubernetes?
10. Что такое GitOps? Как ArgoCD синхронизирует Git и кластер?
11. В чём разница между ConfigMap и Secret в Kubernetes?
12. Как docker-compose.yml для ПСО реализует Database per Service?
13. Зачем нужен Docker Registry?
14. Как health endpoint помогает при rolling update?

---

## Глоссарий

| Термин | Определение |
| ------ | ----------- |
| **DevOps** | Культура и практики доставки ПО (Dev + Ops) |
| **CI** | Continuous Integration - автосборка и тестирование |
| **CD** | Continuous Delivery/Deployment - автодоставка/автодеплой |
| **IaC** | Infrastructure as Code - инфраструктура в коде |
| **GitOps** | IaC + Git как единый источник правды |
| **Docker** | Платформа контейнеризации |
| **Kubernetes** | Система оркестрации контейнеров |
| **Pod** | Минимальная единица запуска в K8s |
| **Deployment** | Управление репликами Pod |
| **Ingress** | HTTP-маршрутизация в K8s |
| **Probe** | Проверка здоровья (liveness/readiness/startup) |
| **ArgoCD** | GitOps-агент для Kubernetes |

---

## Связь с литературной основой курса

- **Характеристики:** Развёртываемость (Docker + K8s), Воспроизводимость (IaC, GitOps), Отказоустойчивость (probes, replicas), Безопасность (non-root, Secrets).
- **Артефакт:** ADR-029 (Docker + Compose), ADR-030 (K8s + GitOps). Файлы: `Dockerfile`, `docker-compose.yml`, `deployment.yaml`, `service.yaml`, `health.py`.
- **Проверка:** `docker-compose up` → all healthy. Pod restarts < 1/час. Rolling update без downtime. Image size < 200 МБ.

---

## Список литературы

### Основная

1. **[О7]** Вольф, Э. Continuous delivery. Практика непрерывных апдейтов. - СПб.: Питер, 2018. - 320 с. - Разделы: пайплайны, контейнеры, деплой.
2. **[О8]** Дэниелс, К., Дэвис, Дж. Философия DevOps. - СПб.: Питер, 2016. - 281 с. - Разделы: культура, коллаборация.
3. **[О9]** Limoncelli, T. et al. The Practice of Cloud Administration. - Addison-Wesley, 2015. - 559 p. - Разделы: release engineering, infrastructure.

### Дополнительная

1. **[Д6]** Бейер, Б. и др. Site Reliability Engineering. - СПб.: Питер, 2019. - 592 с. - Разделы: SLI/SLO, monitoring, release.
2. Docker Documentation - docs.docker.com.
3. Kubernetes Documentation - kubernetes.io/docs.
4. ArgoCD Documentation - argo-cd.readthedocs.io.
