from redis import Redis
from django.conf import settings


class RedisService:
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL)
