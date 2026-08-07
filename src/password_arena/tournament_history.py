import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from password_arena.models import MatchupResult, TournamentConfig


class TournamentHistoryManager:
    def __init__(self, storage_dir: str | Path = ".password_arena_tournaments"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, config: TournamentConfig, matchups: list[MatchupResult]) -> str:
        tournament_id = uuid.uuid4().hex
        timestamp = datetime.now(UTC).isoformat()

        # We only save metadata and experiment links, not the full experiment data
        matchup_data = []
        for m in matchups:
            m_dict = {
                "matchup_id": m.matchup_id,
                "config": asdict(m.config),
                "summary": asdict(m.summary),
                "is_comparable": m.is_comparable,
                "non_comparable_reason": m.non_comparable_reason,
                "experiment_ids": [exp.experiment_id for exp in m.experiments],
            }
            matchup_data.append(m_dict)

        data = {
            "tournament_id": tournament_id,
            "timestamp": timestamp,
            "config": asdict(config),
            "matchups": matchup_data,
        }

        file_path = self.storage_dir / f"{tournament_id}.json"
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return tournament_id
