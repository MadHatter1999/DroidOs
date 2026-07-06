"""Users, roles and authorization (spec §32).

High-risk actions require an authenticated role, not merely recognition of a
familiar voice. The reference build maps identities to roles from ``users.yaml``;
a production build authenticates against a protected credential store.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from ..util import miniyaml

if TYPE_CHECKING:
    from ..core.config import Config


class Role(str, Enum):
    GUEST = "guest"
    OPERATOR = "operator"
    SERVICE_TECHNICIAN = "service_technician"
    OWNER = "owner"

    @property
    def rank(self) -> int:
        return {
            Role.GUEST: 0,
            Role.OPERATOR: 1,
            Role.SERVICE_TECHNICIAN: 2,
            Role.OWNER: 3,
        }[self]


@dataclass
class User:
    name: str
    role: Role
    display_name: str = ""


class Authorizer:
    def __init__(self, config: "Config") -> None:
        self.config = config
        self.users: dict[str, User] = {}
        self._load()

    def _load(self) -> None:
        path = self.config.paths.users_file
        data = {}
        if path.exists():
            data = miniyaml.load_file(str(path)) or {}
        for entry in (data.get("users", []) if isinstance(data, dict) else []):
            try:
                role = Role(entry.get("role", "guest"))
            except ValueError:
                role = Role.GUEST
            user = User(entry["name"], role, entry.get("display_name", ""))
            self.users[user.name] = user
        # always provide the four canonical roles as fallback identities
        for role in Role:
            self.users.setdefault(role.value, User(role.value, role, role.value.title()))

    def resolve(self, name: str | None) -> User:
        if name and name in self.users:
            return self.users[name]
        default = self.config.get("default_user", default="operator")
        return self.users.get(default, User("operator", Role.OPERATOR))

    def authorize(self, user: User, min_role_rank: int) -> tuple[bool, str]:
        if user.role.rank >= min_role_rank:
            return True, "authorized"
        needed = _rank_name(min_role_rank)
        return False, f"requires {needed} authorization; {user.name} is {user.role.value}"


def _rank_name(rank: int) -> str:
    return {0: "guest", 1: "operator", 2: "service technician", 3: "owner"}.get(rank, "owner")
