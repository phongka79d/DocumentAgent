from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IngestionStepDependencies:
    create_supabase_client: Callable[..., Any]
    create_shopaikey_client: Callable[..., Any]
    create_qdrant_client: Callable[..., Any]
    get_parser_for_file: Callable[..., Any]
    relations: Any
