"""Django fixture JSON with full microsecond precision for database migration."""
from datetime import datetime
from django.core.serializers.json import Serializer as JSONSerializer, DjangoJSONEncoder


class PreciseEncoder(DjangoJSONEncoder):
    def default(self, value):
        if isinstance(value, datetime):
            text = value.isoformat(timespec='microseconds')
            return text[:-6] + 'Z' if text.endswith('+00:00') else text
        return super().default(value)


class Serializer(JSONSerializer):
    def _init_options(self):
        super()._init_options()
        self.json_kwargs['cls'] = PreciseEncoder
