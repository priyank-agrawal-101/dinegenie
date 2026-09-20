# Database Migrations

Migrations are ordered SQL files applied by `pipelines.database.apply_migrations`.
SQLite-specific SQL stays behind the repository boundary so a PostgreSQL implementation can
provide its own dialect without changing domain or recommendation code.
