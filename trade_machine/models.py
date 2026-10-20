from dataclasses import dataclass, field


@dataclass(frozen=True)
class Player:
    player_id: int
    name: str
    position: str
    age: int
    salary: int


@dataclass
class Team:
    abbr: str
    players: list[Player] = field(default_factory=list)

    def payroll(self) -> int:
        """Sum of all player salaries."""
        return sum(p.salary for p in self.players)

    def get_player(self, player_id: int) -> Player:
        """Find a player by id. Raise ValueError if not on this team."""
        for p in self.players:
            if p.player_id == player_id:
                return p
        raise ValueError(f"player_id {player_id} is not on {self.abbr}")
