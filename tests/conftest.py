import os

os.environ.setdefault("PROJECT_NAME", "TestProject")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DB_POOL_CLASS", "NullPool")
os.environ.setdefault("TESTING", "true")
