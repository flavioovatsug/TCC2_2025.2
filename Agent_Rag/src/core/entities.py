"""
Entidades do domínio — POO pura, sem dependências externas.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Requirement:
    req_id: str
    text: str
    type: Optional[str] = None
    domain: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None
    community_id: Optional[int] = None
    embedding: List[float] = field(default_factory=list)
    embedding_model: str = "text-embedding-3-small"


@dataclass
class Technique:
    tech_id: str
    name: str
    description: str
    category: str
    source: str = ""


@dataclass
class Instruction:
    instr_id: str
    text: str
    context: str = ""
    source: str = ""


@dataclass
class Concept:
    concept_id: str
    name: str
    definition: str
    source: str = ""
