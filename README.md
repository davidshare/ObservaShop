# ObservaShop
A simple monorepo microservice

## Resource
- https://github.com/iktakahiro/dddpy
- https://github.com/pgorecki/python-ddd
- https://medium.com/@nomannayeem/everything-you-need-to-know-about-domain-driven-design-with-python-microservices-2c2f6556b5b1
- https://dev.to/vortico/native-domain-driven-design-with-flama-l9o

```
.
├── docs
│   ├── api
│   ├── architecture
│   │   └── diagrams
│   └── design
├── infra
│   ├── databases
│   │   ├── analytics
│   │   │   └── init.sql
│   │   ├── auth
│   │   │   └── init.sql
│   │   ├── authz
│   │   │   └── init.sql
│   │   ├── media
│   │   │   └── init.sql
│   │   ├── notification
│   │   │   └── init.sql
│   │   ├── order
│   │   │   └── init.sql
│   │   ├── payment
│   │   │   └── init.sql
│   │   └── product
│   │       └── init.sql
│   ├── docker
│   │   ├── analytics-service.Dockerfile
│   │   ├── auth-service.Dockerfile
│   │   ├── authz-service.Dockerfile
│   │   ├── media-service.Dockerfile
│   │   ├── notification-service.Dockerfile
│   │   ├── order-service.Dockerfile
│   │   ├── payment-service.Dockerfile
│   │   └── product-service.Dockerfile
│   ├── docker-compose-observability.yaml
│   ├── docker-compose-services.yaml
│   ├── docker-compose-tools.yaml
│   ├── gateway
│   │   └── kong
│   │       ├── kong.conf
│   │       ├── kong.yml
│   │       └── plugins
│   ├── infra
│   │   └── databases
│   │       └── auth
│   │           ├── initdb
│   │           └── init.sql
│   ├── kubernetes
│   │   ├── deployments
│   │   ├── helm
│   │   └── services
│   ├── minio
│   │   └── minio-config.yaml
│   └── observability
│       ├── alertmanager
│       │   └── templates
│       ├── grafana
│       │   └── dashboards
│       ├── loki
│       ├── prometheus
│       └── tempo
├── __init__.py
├── main.py
├── pyproject.toml
├── README.md
├── scripts
│   ├── chaos-experiments.sh
│   ├── cleanup-redis.sh
│   ├── generate-docs.sh
│   ├── load-test.sh
│   └── setup-local.sh
├── services
│   ├── analytics_service
│   │   ├── alembic.ini
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src
│   │       ├── application
│   │       ├── config
│   │       │   ├── config.py
│   │       │   ├── __init__.py
│   │       │   └── __pycache__
│   │       │       ├── config.cpython-312.pyc
│   │       │       └── __init__.cpython-312.pyc
│   │       ├── domain
│   │       ├── events
│   │       ├── infrastructure
│   │       │   ├── database
│   │       │   │   ├── alembic
│   │       │   │   │   ├── env.py
│   │       │   │   │   ├── __pycache__
│   │       │   │   │   │   └── env.cpython-312.pyc
│   │       │   │   │   ├── README
│   │       │   │   │   ├── script.py.mako
│   │       │   │   │   └── versions
│   │       │   │   │       ├── d56359dea888_initial_schema.py
│   │       │   │   │       └── __pycache__
│   │       │   │   │           └── d56359dea888_initial_schema.cpython-312.pyc
│   │       │   │   ├── models.py
│   │       │   │   └── __pycache__
│   │       │   │       └── models.cpython-312.pyc
│   │       │   ├── jwt
│   │       │   └── redis
│   │       ├── __init__.py
│   │       ├── interfaces
│   │       │   └── http
│   │       ├── main.py
│   │       ├── __pycache__
│   │       │   └── __init__.cpython-312.pyc
│   │       └── start.py
│   ├── auth_service
│   │   ├── alembic.ini
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   └── __init__.cpython-312.pyc
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── src
│   │   │   ├── application
│   │   │   ├── config
│   │   │   │   ├── config.py
│   │   │   │   ├── __init__.py
│   │   │   │   └── __pycache__
│   │   │   │       ├── config.cpython-312.pyc
│   │   │   │       └── __init__.cpython-312.pyc
│   │   │   ├── domain
│   │   │   ├── events
│   │   │   ├── infrastructure
│   │   │   │   ├── database
│   │   │   │   │   ├── alembic
│   │   │   │   │   │   ├── env.py
│   │   │   │   │   │   ├── __pycache__
│   │   │   │   │   │   │   └── env.cpython-312.pyc
│   │   │   │   │   │   ├── README
│   │   │   │   │   │   ├── script.py.mako
│   │   │   │   │   │   └── versions
│   │   │   │   │   │       ├── 78c59c87ff5a_initial_schema.py
│   │   │   │   │   │       └── __pycache__
│   │   │   │   │   │           └── 78c59c87ff5a_initial_schema.cpython-312.pyc
│   │   │   │   │   ├── models.py
│   │   │   │   │   └── __pycache__
│   │   │   │   │       └── models.cpython-312.pyc
│   │   │   │   ├── jwt
│   │   │   │   └── redis
│   │   │   ├── __init__.py
│   │   │   ├── interfaces
│   │   │   │   └── http
│   │   │   ├── main.py
│   │   │   ├── __pycache__
│   │   │   │   └── __init__.cpython-312.pyc
│   │   │   └── start.py
│   │   └── uv.lock
│   ├── authz_service
│   │   ├── alembic.ini
│   │   ├── __init__.py
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── src
│   │   │   ├── application
│   │   │   │   └── __init__.py
│   │   │   ├── config
│   │   │   │   ├── config.py
│   │   │   │   ├── __init__.py
│   │   │   │   └── __pycache__
│   │   │   │       ├── config.cpython-312.pyc
│   │   │   │       └── __init__.cpython-312.pyc
│   │   │   ├── domain
│   │   │   │   └── __init__.py
│   │   │   ├── events
│   │   │   │   └── __init__.py
│   │   │   ├── infrastructure
│   │   │   │   ├── database
│   │   │   │   │   ├── alembic
│   │   │   │   │   │   ├── env.py
│   │   │   │   │   │   ├── __pycache__
│   │   │   │   │   │   │   └── env.cpython-312.pyc
│   │   │   │   │   │   ├── README
│   │   │   │   │   │   ├── script.py.mako
│   │   │   │   │   │   └── versions
│   │   │   │   │   │       ├── bba9ba30bb21_initial_schema.py
│   │   │   │   │   │       └── __pycache__
│   │   │   │   │   │           └── bba9ba30bb21_initial_schema.cpython-312.pyc
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── models.py
│   │   │   │   │   └── __pycache__
│   │   │   │   │       ├── __init__.cpython-312.pyc
│   │   │   │   │       └── models.cpython-312.pyc
│   │   │   │   ├── __init__.py
│   │   │   │   ├── jwt
│   │   │   │   ├── __pycache__
│   │   │   │   │   └── __init__.cpython-312.pyc
│   │   │   │   └── redis
│   │   │   ├── interfaces
│   │   │   │   └── http
│   │   │   ├── main.py
│   │   │   └── start.py
│   │   └── uv.lock
│   ├── __init__.py
│   ├── media_service
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src
│   │       ├── application
│   │       ├── config
│   │       ├── domain
│   │       ├── events
│   │       ├── infrastructure
│   │       │   ├── database
│   │       │   ├── jwt
│   │       │   └── redis
│   │       └── interfaces
│   │           └── http
│   ├── notification-service
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src
│   │       ├── application
│   │       ├── config
│   │       ├── domain
│   │       ├── events
│   │       ├── infrastructure
│   │       │   ├── database
│   │       │   ├── jwt
│   │       │   └── redis
│   │       └── interfaces
│   │           └── http
│   ├── order-service
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src
│   │       ├── application
│   │       ├── config
│   │       ├── domain
│   │       ├── events
│   │       ├── infrastructure
│   │       │   ├── database
│   │       │   ├── jwt
│   │       │   └── redis
│   │       └── interfaces
│   │           └── http
│   ├── payment-service
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src
│   │       ├── application
│   │       ├── config
│   │       ├── domain
│   │       ├── events
│   │       ├── infrastructure
│   │       │   ├── database
│   │       │   ├── jwt
│   │       │   └── redis
│   │       └── interfaces
│   │           └── http
│   ├── product-service
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src
│   │       ├── application
│   │       ├── config
│   │       ├── domain
│   │       ├── events
│   │       ├── infrastructure
│   │       │   ├── database
│   │       │   ├── jwt
│   │       │   └── redis
│   │       └── interfaces
│   │           └── http
│   └── __pycache__
│       └── __init__.cpython-312.pyc
├── shared
│   ├── config
│   │   ├── env.template
│   │   └── logging.yaml
│   ├── libs
│   │   ├── auth
│   │   ├── kafka
│   │   ├── minio
│   │   ├── observability
│   │   ├── rabbitmq
│   │   └── redis
│   └── schemas
├── tests
│   ├── chaos
│   ├── integration
│   └── load
└── uv.lock
```