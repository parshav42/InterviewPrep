import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def parse_structured(text: str, schema: type[T]) -> T:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else candidate
        candidate = candidate.rsplit("```", 1)[0].strip()
    decoder = json.JSONDecoder()
    candidates = [candidate]
    candidates.extend(candidate[index:] for index, character in enumerate(candidate) if character in "[{" and index)
    for possible in candidates:
        try:
            payload = json.loads(possible) if possible is candidate else decoder.raw_decode(possible)[0]
        except json.JSONDecodeError:
            continue
        try:
            return schema.model_validate(payload)
        except ValidationError:
            continue
    raise ValueError("LLM response was not valid JSON matching the expected schema")
