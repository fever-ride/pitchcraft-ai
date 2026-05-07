from enum import Enum


class FallbackLevel(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    INTERNAL_ONLY = "internal_only"
    TEMPLATE = "template"


class FallbackChain:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.current_level = FallbackLevel.PRIMARY

    async def execute(self, primary_fn, secondary_fn=None, fallback_fn=None):
        try:
            result = await primary_fn()
            self.current_level = FallbackLevel.PRIMARY
            return result, self.current_level
        except Exception:
            pass

        if secondary_fn:
            try:
                result = await secondary_fn()
                self.current_level = FallbackLevel.SECONDARY
                return result, self.current_level
            except Exception:
                pass

        if fallback_fn:
            result = await fallback_fn()
            self.current_level = FallbackLevel.INTERNAL_ONLY
            return result, self.current_level

        self.current_level = FallbackLevel.TEMPLATE
        return None, self.current_level
