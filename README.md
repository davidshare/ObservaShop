# ObservaShop
A simple monorepo microservice

## Resource
- https://github.com/iktakahiro/dddpy
- https://github.com/pgorecki/python-ddd
- https://medium.com/@nomannayeem/everything-you-need-to-know-about-domain-driven-design-with-python-microservices-2c2f6556b5b1
- https://dev.to/vortico/native-domain-driven-design-with-flama-l9o

```
observashop/
├── .github/                          # GitHub Actions for CI/CD
│   └── workflows/
│       ├── ci.yml
│       ├── cd.yml
│       └── chaos.yml
├── docs/                             # Documentation
│   ├── architecture/
│   │   ├── sad.md
│   │   └── diagrams/
│   ├── design/
│   │   ├── sdd.md
│   │   └── prd.md
│   ├── api/
│   │   └── endpoints.md
│   └── setup.md
├── infra/                            # Infrastructure configurations
│   ├── docker/                   # Dockerfiles for services
│   │   ├── auth-service.Dockerfile
│   │   ├── authz-service.Dockerfile
│   │   ├── product-service.Dockerfile
│   │   ├── order-service.Dockerfile
│   │   ├── payment-service.Dockerfile
│   │   ├── notification-service.Dockerfile
│   │   ├── media-service.Dockerfile
│   │   ├── analytics-service.Dockerfile
│   │   └── kong.Dockerfile
│   ├── docker-compose-tools.yml  # Tools (Kong, Redis, MinIO, Kafka, DBs, observability)
│   ├── docker-compose-services.yml # Microservices
│   ├── gateway/                  # Kong gateway configurations
│   │   ├── kong/
│   │   │   ├── kong.yml
│   │   │   ├── plugins/
│   │   │   │   ├── jwt.lua
│   │   │   │   ├── rbac.lua
│   │   │   │   └── prometheus.lua
│   │   │   └── kong.conf
│   ├── kubernetes/               # Optional Kubernetes manifests
│   │   ├── deployments/
│   │   ├── services/
│   │   └── helm/
│   ├── minio/                    # MinIO configuration
│   │   ├── minio-config.yaml
│   │   └── bucket-policies.json
│   ├── databases/                # Per-service database configurations
│   │   ├── auth/                 # SQLite or PostgreSQL config
│   │   │   └── init.sql         # Initial schema (if SQLite)
│   │   ├── authz/                # PostgreSQL config
│   │   │   └── init.sql         # Initial schema
│   │   ├── product/              # PostgreSQL config
│   │   │   └── init.sql
│   │   ├── order/                # PostgreSQL config
│   │   │   └── init.sql
│   │   ├── payment/              # PostgreSQL config
│   │   │   └── init.sql
│   │   ├── notification/         # PostgreSQL config (if used)
│   │   │   └── init.sql
│   │   ├── media/                # PostgreSQL config
│   │   │   └── init.sql
│   │   └── analytics/            # PostgreSQL config
│   │       └── init.sql
│   └── observability/            # Observability stack configs
│       ├── prometheus/
│       │   ├── prometheus.yml
│       │   └── alerting-rules.yml
│       ├── grafana/
│       │   ├── dashboards/
│       │   │   ├── auth.json
│       │   │   ├── kong.json
│       │   │   └── overview.json
│       │   └── grafana.ini
│       ├── loki/
│       │   ├── loki-config.yaml
│       │   └── retention.yaml
│       ├── tempo/
│       │   ├── tempo.yaml
│       │   └── tracing-rules.yaml
│       └── alertmanager/
│           ├── alertmanager.yml
│           └── templates/
├── scripts/                          # Utility scripts
│   ├── setup-local.sh            # Sets up tools and services
│   ├── chaos-experiments.sh
│   ├── load-test.sh
│   ├── generate-docs.sh
│   └── cleanup-redis.sh
├── services/                         # Microservices
│   ├── auth-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   ├── repositories/
│   │   │   │   ├── jwt/
│   │   │   │   ├── redis/
│   │   │   │   └── database/     # Migrations for SQLite/PostgreSQL
│   │   │   ├── interfaces/
│   │   │   │   ├── http/
│   │   │   │   └── cli/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── authz-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── database/     # PostgreSQL migrations
│   │   │   ├── interfaces/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── product-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── database/     # PostgreSQL migrations
│   │   │   ├── interfaces/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── order-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── database/     # PostgreSQL migrations
│   │   │   ├── interfaces/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── payment-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── database/     # PostgreSQL migrations
│   │   │   ├── interfaces/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── notification-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── database/     # PostgreSQL migrations (if used)
│   │   │   ├── interfaces/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── media-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── database/     # PostgreSQL migrations
│   │   │   ├── interfaces/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── analytics-service/
│   │   ├── src/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   │   └── database/     # PostgreSQL migrations
│   │   │   ├── interfaces/
│   │   │   ├── events/
│   │   │   └── config/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
├── shared/                           # Shared libraries and configs
│   ├── libs/
│   │   ├── auth/
│   │   │   ├── jwt_utils.py
│   │   │   ├── refresh_token_utils.py
│   │   │   └── authz_client.py
│   │   ├── observability/
│   │   │   ├── logging.py
│   │   │   ├── metrics.py
│   │   │   └── tracing.py
│   │   ├── kafka/
│   │   │   ├── producer.py
│   │   │   └── consumer.py
│   │   ├── rabbitmq/
│   │   │   ├── producer.py
│   │   │   └── consumer.py
│   │   ├── redis/
│   │   │   └── client.py
│   │   └── minio/
│   │       └── client.py
│   ├── schemas/
│   │   ├── auth.events.json
│   │   ├── order.events.json
│   │   ├── payment.events.json
│   │   ├── product.events.json
│   │   ├── media.events.json
│   │   ├── notification.events.json
│   │   ├── authz.events.json
│   │   └── analytics.events.json
│   └── config/
│       ├── env.template
│       └── logging.yaml
├── tests/                            # Cross-service tests
│   ├── integration/
│   │   ├── test_auth.py
│   │   ├── test_orders.py
│   │   └── test_payments.py
│   ├── load/
│   │   ├── locustfile.py
│   │   └── results/
│   └── chaos/
│       ├── latency.yaml
│       ├── crash.yaml
│       └── queue-overflow.yaml
├── pyproject.toml                # Monorepo-wide Python dependencies
├── README.md                     # Project overview
├── LICENSE
└── .gitignore
```