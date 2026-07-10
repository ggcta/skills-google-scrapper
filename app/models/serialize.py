import json
from collections.abc import Mapping

# Class to serialize objects to JSON
class Serialize:

    # Convert object to dictionary containing non-private attributes
    def to_dict(self) -> Mapping[str, object]:
        # `object.__dict__` is typed `dict[str, Any]` by typeshed since instance
        # attributes are inherently heterogeneous; there's no way to narrow this
        # generically for an arbitrary subclass. `Mapping` (covariant in value
        # type) lets overrides declare a narrower value type than `object`.
        return {key.lstrip('_'): value for key, value in self.__dict__.items()}  # pyright: ignore[reportAny]

    # Convert object to JSON string
    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
