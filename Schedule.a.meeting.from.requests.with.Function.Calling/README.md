## Modular / Feature-Based Architecture (Recommended for Medium-to-Large Apps)
Each domain or feature gets its own directory containing its models, schemas, services, routes, and tasks. This keeps related code grouped together.

```my_project/
├── app/
│   ├── modules/
│   │   ├── calendar/
│   │   │   ├── router.py
│   │   │   ├── services.py
│   │   │   ├── models.py
│   │   │   └── tasks.py         # <-- Calendar-specific tasks
│   │   ├── email/
│   │   │   ├── services.py
│   │   │   └── tasks.py         # <-- Email-specific tasks
│   │   └── notifications/
│   │       └── tasks.py
│   ├── config/
│   │   ├── database.py
│   │   └── settings.py
│   ├── main.py
│   └── celery_app.py
```

### Crucial Celery Auto-Discovery Requirement
1. Regardless of which folder structure you choose, Celery must be able to locate and register your task functions.
2. Instead of manually importing every task file, you configure Celery’s autodiscover_tasks in your celery_app.py:

```
# celery_app.py
from celery import Celery

celery_app = Celery("my_app")
celery_app.config_from_object("app.config.celery_config")

# Auto-discovers any tasks.py or *_tasks.py in listed packages
celery_app.autodiscover_tasks([
    "app.modules.calendar",
    "app.modules.email",
    # OR if using a dedicated tasks folder:
    # "app.tasks"
])
```

## Centrally Dedicated Architecture (Best for Small-to-Medium Apps)
If background jobs share heavy utility code or pipeline logic, developers create a dedicated tasks/ or background_tasks/ package at the app level, split by domain file names.

```
my_project/
├── app/
│   ├── routes/
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── calendar_tasks.py    # <-- Calendar tasks
│   │   ├── email_tasks.py       # <-- Email tasks
│   │   └── maintenance_tasks.py
│   ├── services/
│   │   └── google_calendar.py
│   │   └── llm_usage_tracker.py
│   ├── config/
│   │   ├── database.py
│   │   └── settings.py
│   └── main.py
│   └── celery_app.py
```