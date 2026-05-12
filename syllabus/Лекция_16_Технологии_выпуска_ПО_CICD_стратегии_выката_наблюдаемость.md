# Лекция 16. Технологии выпуска ПО: CI/CD, окружения, наблюдаемость, стратегии выката

> **Дисциплина:** Проектирование интернет-систем (ПИС)
> **Курс:** 3, Семестр: 6
> **Тема по учебной программе:** Тема 16 - Технологии выпуска ПО
> **ADR-диапазон:** ADR-031 - ADR-032

---

## Результаты обучения

После лекции студент сможет:

1. Описать **конвейер CI/CD** (pipeline): сборка → тестирование → анализ → деплой → эксплуатация.
2. Настроить **GitHub Actions** workflow для микросервиса.
3. Объяснить **типы окружений** (dev, staging, production) и их назначение.
4. Сравнить **стратегии выката**: rolling update, blue-green, canary.
5. Описать основы **наблюдаемости** (логи, метрики, трейсы) как требования к релизу.
6. Объяснить роль **безопасности** (секреты, SAST/DAST) в пайплайне.

---

## Пререквизиты

- Docker и docker-compose из **лекции 15** (Dockerfile, контейнеризация).
- Kubernetes из **лекции 15** (Deployment, Service, Ingress, Probes).
- GitOps из **лекции 15** (Git как единый источник правды).
- Тестирование: unit/integration/E2E (упоминалось в лекциях 07-09).

---

## 1. Введение: зачем автоматизировать выпуск

### Проблема

Ручной деплой: разработчик собирает артефакт, копирует на сервер, запускает. Проблемы:

- **Человеческий фактор**: забыл запустить тесты, перепутал конфиг.
- **Не воспроизводимо**: «я деплоил руками, и что-то пошло не так».
- **Долго**: 2 дня разработки + 2 часа ручного деплоя → релиз раз в месяц.
- **Страх**: «лучше не деплоить в пятницу».

### Цель CI/CD

> **[О7] Вольф:** «Continuous Delivery - это способность выпустить новую версию системы в production в любой момент, безопасно и быстро.»

**Цель:** от commit до production за **минуты**, а не дни. Каждый коммит - потенциальный релиз.

---

## 2. Основные понятия и терминология

**Определения:**

- **Pipeline (конвейер)** - последовательность автоматических шагов: сборка → тесты → анализ → деплой.
- **Artifact (артефакт)** - результат сборки (Docker image, wheel, JAR).
- **Environment (окружение)** - среда выполнения (dev, staging, production).
- **Rolling Update** - постепенная замена контейнеров (Kubernetes default).
- **Blue-Green Deployment** - два идентичных окружения; переключение трафика.
- **Canary Deployment** - новая версия получает малую долю трафика.
- **SAST (Static Application Security Testing)** - анализ безопасности исходного кода.
- **DAST (Dynamic Application Security Testing)** - тестирование безопасности работающего приложения.
- **SLI (Service Level Indicator)** - метрика качества сервиса (latency, error rate).
- **SLO (Service Level Objective)** - целевое значение SLI (p99 latency < 200ms).

---

## 3. Конвейер CI/CD: этапы

```mermaid
graph LR
    A["1. Code<br/>git push"] --> B["2. Build<br/>docker build"]
    B --> C["3. Test<br/>unit + integration"]
    C --> D["4. Analyze<br/>SAST, lint, coverage"]
    D --> E["5. Publish<br/>push to registry"]
    E --> F["6. Deploy<br/>staging → prod"]
    F --> G["7. Verify<br/>smoke tests, SLI/SLO"]

    style A fill:#e8f5e9
    style G fill:#e3f2fd
```

| Этап | Что происходит | Инструменты |
| ---- | -------------- | ----------- |
| **Code** | Разработчик пушит код | Git, GitHub |
| **Build** | Сборка Docker-образа | Docker, BuildKit |
| **Test** | Unit-тесты, integration-тесты | pytest, testcontainers |
| **Analyze** | Линтинг, покрытие, SAST | ruff, coverage.py, bandit/semgrep |
| **Publish** | Push образа в registry | GHCR, Harbor |
| **Deploy** | Развёртывание | ArgoCD, kubectl, Helm |
| **Verify** | Smoke-тесты, проверка SLI | httpx, Prometheus, Grafana |

---

## 4. GitHub Actions: пример CI/CD для dispatch-service

```yaml
# .github/workflows/dispatch-ci.yml

name: Dispatch Service CI/CD

on:
  push:
    branches: [main]
    paths:
      - "dispatch-service/**"
  pull_request:
    branches: [main]
    paths:
      - "dispatch-service/**"

env:
  IMAGE_NAME: ghcr.io/${{ github.repository_owner }}/dispatch-service
  PYTHON_VERSION: "3.12"

jobs:
  # --- Этап 1: Тестирование ---
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: dispatch_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U test"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        working-directory: dispatch-service
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Run linter (ruff)
        working-directory: dispatch-service
        run: ruff check .

      - name: Run tests with coverage
        working-directory: dispatch-service
        env:
          DATABASE_URL: "postgresql://test:test@localhost:5432/dispatch_test"
        run: |
          pytest --cov=dispatch --cov-report=xml --cov-report=term -v

      - name: Check coverage threshold
        working-directory: dispatch-service
        run: |
          coverage report --fail-under=80

      - name: SAST scan (bandit)
        working-directory: dispatch-service
        run: bandit -r dispatch/ -f json -o bandit-report.json || true

  # --- Этап 2: Сборка и публикация образа ---
  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: dispatch-service
          push: true
          tags: |
            ${{ env.IMAGE_NAME }}:${{ github.sha }}
            ${{ env.IMAGE_NAME }}:latest

  # --- Этап 3: Деплой на staging ---
  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - uses: actions/checkout@v4

      - name: Update image tag in GitOps repo
        run: |
          python scripts/update_image_tag.py \
            k8s/staging/dispatch-deployment.yaml \
            ${{ github.sha }}

      - name: Commit and push
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add .
          git commit -m "deploy: dispatch-service ${{ github.sha }}"
          git push

  # --- Этап 4: Smoke test ---
  verify-staging:
    needs: deploy-staging
    runs-on: ubuntu-latest

    steps:
      - name: Wait for deployment
        run: sleep 30

      - name: Smoke test
        run: |
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://staging.pso.example.com/api/v1/requests)
          if [ "$STATUS" != "200" ]; then
            echo "Smoke test failed: HTTP $STATUS"
            exit 1
          fi
          echo "Smoke test passed: HTTP $STATUS"
```

**Пояснение к workflow:**

- **Матричная зависимость**: test → build → deploy-staging → verify-staging.
- **PostgreSQL service** - реальная БД в CI для integration-тестов.
- **coverage --fail-under=80** - если покрытие < 80%, пайплайн ломается.
- **SAST (bandit)** - статический анализ безопасности Python-кода.
- **GitOps**: workflow обновляет тег образа в GitOps-репозитории → ArgoCD подхватит.

---

## 5. Типы окружений

| Окружение | Назначение | Данные | Кто использует |
| --------- | ---------- | ------ | -------------- |
| **dev (local)** | Разработка | Фикстуры / моки | Разработчик |
| **CI** | Автотесты | Тестовая БД (ephemeral) | Pipeline |
| **staging** | Предрелизная проверка | Копия prod (анонимизированные) | QA, Product Owner |
| **production** | Реальные пользователи | Реальные данные | Конечные пользователи |

### Принципы

1. **Parity (паритет)**: staging ≈ production (те же версии ПО, ОС, конфиг).
2. **Ephemeral CI**: тестовые БД создаются и удаляются при каждом запуске.
3. **Secrets per environment**: каждое окружение - свои credentials.
4. **Promotion**: образ `dispatch:abc123` промотируется dev → staging → prod (один образ!).

---

## 6. Стратегии выката и отката

### Rolling Update (по умолчанию в Kubernetes)

```yaml
# k8s/dispatch-deployment.yaml (фрагмент)
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # +1 Pod во время обновления
      maxUnavailable: 0   # всегда минимум N Pods доступны
```

- **Как работает:** Kubernetes создаёт новый Pod → проверяет readinessProbe → убирает старый Pod → повторяет.
- **Откат:** `kubectl rollout undo deployment/dispatch-service`.
- **Плюсы:** простота, zero downtime.
- **Минусы:** нет контроля трафика (оба версии обслуживают параллельно).

### Blue-Green Deployment

```mermaid
graph LR
    LB["Load Balancer"]
    subgraph "Blue (v1.0 - active)"
        B1["Pod v1.0"]
        B2["Pod v1.0"]
    end
    subgraph "Green (v1.1 - idle)"
        G1["Pod v1.1"]
        G2["Pod v1.1"]
    end

    LB -->|"100% traffic"| B1
    LB -->|"100% traffic"| B2
    LB -.->|"0% (switch)"| G1
    LB -.->|"0% (switch)"| G2

    style B1 fill:#bbdefb
    style B2 fill:#bbdefb
    style G1 fill:#c8e6c9
    style G2 fill:#c8e6c9
```

- **Как работает:** два полных окружения (Blue = текущее, Green = новое). Тестируем Green → переключаем трафик.
- **Откат:** мгновенный - переключаем обратно на Blue.
- **Плюсы:** мгновенное переключение и откат.
- **Минусы:** двойные ресурсы.

### Canary Deployment

- **Как работает:** новая версия получает 5% трафика → мониторим SLI → 25% → 50% → 100%.
- **Откат:** направить 100% обратно на старую версию.
- **Плюсы:** минимальный риск (проблемы затронут мало пользователей).
- **Минусы:** сложнее реализовать (нужен ingress с весами).

```python
# scripts/canary_check.py - проверка SLI перед увеличением трафика

"""Скрипт проверки SLI во время canary-деплоя."""

import httpx
import sys

PROMETHEUS_URL = "http://prometheus:9090/api/v1/query"

def check_error_rate(service: str, threshold: float = 0.01) -> bool:
    """Проверить error rate < threshold (1%)."""
    query = (
        f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m]))'
        f' / sum(rate(http_requests_total{{service="{service}"}}[5m]))'
    )
    response = httpx.get(PROMETHEUS_URL, params={"query": query})
    result = response.json()["data"]["result"]
    if not result:
        print(f"No data for {service}")
        return True  # Нет данных - пропускаем
    error_rate = float(result[0]["value"][1])
    print(f"Error rate for {service}: {error_rate:.4f} (threshold: {threshold})")
    return error_rate < threshold

def check_latency_p99(service: str, threshold_ms: float = 200) -> bool:
    """Проверить p99 latency < threshold."""
    query = (
        f'histogram_quantile(0.99, '
        f'sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) '
        f'by (le))'
    )
    response = httpx.get(PROMETHEUS_URL, params={"query": query})
    result = response.json()["data"]["result"]
    if not result:
        return True
    latency_ms = float(result[0]["value"][1]) * 1000
    print(f"P99 latency for {service}: {latency_ms:.1f}ms (threshold: {threshold_ms}ms)")
    return latency_ms < threshold_ms

if __name__ == "__main__":
    service = sys.argv[1] if len(sys.argv) > 1 else "dispatch-service"
    ok = check_error_rate(service) and check_latency_p99(service)
    sys.exit(0 if ok else 1)
```

### Сравнение стратегий

| Критерий | Rolling Update | Blue-Green | Canary |
| -------- | -------------- | ---------- | ------ |
| **Сложность** | Низкая | Средняя | Высокая |
| **Ресурсы** | N+1 Pod | 2N Pods | N+1 Pod |
| **Откат** | `rollout undo` | Мгновенный | Мгновенный |
| **Контроль трафика** | Нет | Да (переключение) | Да (проценты) |
| **Риск** | Средний | Низкий | **Минимальный** |
| **Рекомендация** | По умолчанию | Критические сервисы | High-traffic |

---

## 7. Наблюдаемость как требование к релизу

### Три столпа наблюдаемости

| Столп | Что | Инструменты | Пример |
| ----- | --- | ----------- | ------ |
| **Логи** | Текстовые записи событий | Loki, ELK, CloudWatch Logs | `[INFO] Request abc123 created` |
| **Метрики** | Числовые измерения (counters, gauges, histograms) | Prometheus, Grafana | `http_requests_total{status="200"}` |
| **Трейсы** | Путь запроса через сервисы | OpenTelemetry, Jaeger | dispatch → operations → resources |

### SLI/SLO для ПСО «Юго-Запад»

| SLI (метрика) | SLO (цель) | Как измеряем |
| ------------- | ---------- | ------------ |
| **Availability** | 99.9% uptime | `1 - (5xx_requests / total_requests)` |
| **Latency (p99)** | < 200ms | `histogram_quantile(0.99, ...)` |
| **Error rate** | < 1% | `rate(5xx_requests[5m]) / rate(total[5m])` |
| **Throughput** | > 100 req/s | `rate(http_requests_total[1m])` |

### Пример: структурированное логирование (Python)

```python
# dispatch-service/infrastructure/logging_config.py

import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Структурированный JSON-формат для логов."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "service": "dispatch-service",
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        # Добавляем extra-поля (request_id, trace_id)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        return json.dumps(log_entry)

def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
```

```python
# Использование в коде
import logging

logger = logging.getLogger(__name__)

def create_request(body):
    logger.info(
        "Request created",
        extra={"request_id": str(request.id), "type": body.type},
    )
```

---

## 8. Безопасность в пайплайне

### Практики

| Практика | Этап | Инструмент | Что проверяет |
| -------- | ---- | ---------- | ------------- |
| **SAST** | Build/Test | bandit, semgrep | Уязвимости в коде (SQL injection, hardcoded secrets) |
| **Dependency scan** | Build | pip-audit, safety | Уязвимые зависимости (CVE) |
| **Container scan** | Build | trivy, grype | Уязвимости в Docker-образе |
| **Secret scan** | Pre-commit | gitleaks, detect-secrets | Секреты в коде (API keys, passwords) |
| **DAST** | Deploy (staging) | OWASP ZAP | Уязвимости работающего приложения |

### Пример: добавляем сканирование в GitHub Actions

```yaml
# Добавить в .github/workflows/dispatch-ci.yml (job: test)

      - name: Dependency audit
        working-directory: dispatch-service
        run: pip-audit --strict

      - name: Container scan (trivy)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: table
          exit-code: 1
          severity: CRITICAL,HIGH
```

---

## 9. ADR: закрепляем решения

### ADR-031: GitHub Actions CI/CD с coverage gate

| Поле | Значение |
| ---- | -------- |
| **Контекст** | Нужен автоматический конвейер: тесты, lint, SAST, сборка образа, деплой. Ручной деплой - risk + bottleneck. |
| **Решение** | GitHub Actions: test (pytest + ruff + bandit + coverage≥80%) → build (docker + push to GHCR) → deploy (GitOps tag update) → verify (smoke test). |
| **Альтернативы** | (a) GitLab CI - аналогичные возможности, привязка к GitLab. (b) Jenkins - мощнее, но тяжелее в обслуживании. (c) CircleCI - cloud-first, дороже. |
| **Затрагиваемые характеристики** | Скорость доставки ↑, Качество ↑ (coverage gate), Безопасность ↑ (SAST/audit) |
| **Последствия** | Каждый сервис - свой workflow (paths filter). Нужен GHCR (или альтернативный registry). Coverage gate может блокировать merge. |
| **Проверка** | Pipeline green time < 10 min. Coverage ≥ 80%. 0 critical SAST findings. Smoke test passes. |

### ADR-032: Rolling Update по умолчанию, Canary для critical paths

| Поле | Значение |
| ---- | -------- |
| **Контекст** | Три микросервиса деплоятся на Kubernetes. Нужна стратегия выката с минимальным downtime. |
| **Решение** | Rolling Update (maxSurge=1, maxUnavailable=0) - стратегия по умолчанию. Canary (5%→25%→100%) - для dispatch-service (критический путь, high traffic). SLI-гейт: error_rate < 1%, p99 < 200ms. |
| **Альтернативы** | (a) Blue-Green - двойные ресурсы, проще откат. (b) только Rolling Update - нет контроля трафика для critical paths. |
| **Затрагиваемые характеристики** | Доступность ↑ (zero downtime), Риск ↓ (canary для критических), Сложность ↑ (canary инфраструктура) |
| **Последствия** | Нужен Ingress с поддержкой traffic splitting (Nginx Ingress / Istio). canary_check.py в pipeline. Prometheus + SLI метрики обязательны. |
| **Проверка** | Rolling update: 0 5xx during deploy. Canary: error_rate < 1% before promotion. Rollback time < 30 sec. |

---

## Типичные ошибки и антипаттерны

| № | Ошибка | Как исправить |
| - | ------ | ------------- |
| 1 | Нет тестов в CI (push → deploy) | coverage gate ≥ 80%, fail on test failure |
| 2 | Нет smoke-теста after deploy | verify-staging job в pipeline |
| 3 | Один образ не промотируется (пересборка для prod) | Build once → promote same image tag |
| 4 | Секреты в коде / YAML | Secret scan (gitleaks), K8s Secrets, Vault |
| 5 | staging ≠ production | Parity: те же версии ПО, конфиг (кроме secrets) |
| 6 | Нет логов / метрик / трейсов | Структурированные логи + Prometheus + OpenTelemetry |
| 7 | Нет SLI/SLO (непонятно, работает ли) | Определить 3-4 SLI с пороговыми SLO |
| 8 | Деплой без возможности отката | Rolling update с rollout undo; canary с авто-откатом |

---

## Вопросы для самопроверки

1. Что такое CI/CD? Чем Continuous Delivery отличается от Continuous Deployment?
2. Перечислите этапы CI/CD-конвейера. Что происходит на каждом?
3. Зачем нужен coverage gate (--fail-under=80)?
4. Что такое SAST? Какие инструменты используются для Python?
5. Чем Rolling Update отличается от Blue-Green Deployment?
6. Когда использовать Canary Deployment? Какие SLI проверять?
7. Что такое SLI и SLO? Приведите примеры для ПСО «Юго-Запад».
8. Зачем нужен парциальный (parity) staging?
9. Почему один и тот же Docker-образ промотируется через окружения?
10. Что такое smoke test? Зачем его запускать в pipeline?
11. Какие три столпа наблюдаемости? Чем трейс отличается от лога?
12. Зачем нужен структурированный (JSON) формат логов?
13. Как canary_check.py использует Prometheus для проверки SLI?
14. Как выполнить откат в Kubernetes (Rolling Update)?
15. Зачем сканировать Docker-образ (trivy) в pipeline?

---

## Глоссарий

| Термин | Определение |
| ------ | ----------- |
| **CI** | Continuous Integration - автосборка и тестирование |
| **CD** | Continuous Delivery/Deployment - автодоставка/автодеплой |
| **Pipeline** | Последовательность автоматических шагов выпуска |
| **Artifact** | Результат сборки (Docker image) |
| **Rolling Update** | Постепенная замена контейнеров (K8s default) |
| **Blue-Green** | Два окружения, мгновенное переключение трафика |
| **Canary** | Новая версия получает малую долю трафика |
| **SLI** | Service Level Indicator - метрика качества |
| **SLO** | Service Level Objective - целевое значение SLI |
| **SAST** | Статический анализ безопасности кода |
| **DAST** | Динамический анализ безопасности |
| **Observability** | Наблюдаемость: логи + метрики + трейсы |

---

## Связь с литературной основой курса

- **Характеристики:** Развёртываемость (CI/CD), Наблюдаемость (логи, метрики, трейсы), Безопасность (SAST, secret scan, container scan), Надёжность (SLI/SLO, canary с авто-откатом).
- **Артефакт:** ADR-031 (GitHub Actions CI/CD), ADR-032 (Rolling Update + Canary). Файлы: `.github/workflows/dispatch-ci.yml`, `canary_check.py`, `logging_config.py`, K8s rolling update конфиг.
- **Проверка:** Pipeline green < 10 min. Coverage ≥ 80%. 0 critical SAST. Error rate < 1% при canary. Rollback < 30 sec. SLI/SLO дашборд в Grafana.

---

## Список литературы

### Основная

1. **[О7]** Вольф, Э. Continuous delivery. Практика непрерывных апдейтов. - СПб.: Питер, 2018. - 320 с. - Разделы: pipeline, trunk-based development, feature toggles, release strategies.
2. **[О8]** Дэниелс, К., Дэвис, Дж. Философия DevOps. - СПб.: Питер, 2016. - 281 с. - Разделы: культура, коллаборация, blameless postmortems.
3. **[О9]** Limoncelli, T. et al. The Practice of Cloud Administration. - Addison-Wesley, 2015. - 559 p. - Разделы: release engineering, monitoring, on-call.

### Дополнительная

1. **[Д6]** Бейер, Б. и др. Site Reliability Engineering. - СПб.: Питер, 2019. - 592 с. - Разделы: SLI/SLO/SLA, error budgets, toil reduction.
2. GitHub Actions Documentation - docs.github.com/actions.
3. Kubernetes Deployment Strategies - kubernetes.io/docs.
4. OpenTelemetry Documentation - opentelemetry.io/docs.
