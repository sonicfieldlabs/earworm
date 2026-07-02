# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class EarwormReader:
    session: JsonObject

    @classmethod
    def from_file(cls, path: str | Path) -> "EarwormReader":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    @property
    def events(self) -> list[JsonObject]:
        return list(self.session.get("events", []))

    @property
    def assets(self) -> list[JsonObject]:
        return list(self.session.get("assets", []))

    @property
    def provenance(self) -> list[JsonObject]:
        return list(self.session.get("provenance", []))

    def events_for_asset(self, asset_id: str) -> list[JsonObject]:
        return [event for event in self.events if asset_id in _asset_ids_for_event(event)]

    def context_for_asset(self, asset_id: str) -> JsonObject:
        events = self.events_for_asset(asset_id)
        provenance_ids = {
            event.get("provenance_id")
            for event in events
            if isinstance(event.get("provenance_id"), str)
        }
        assets = [asset for asset in self.assets if asset.get("asset_id") == asset_id]
        for asset in assets:
            provenance_id = asset.get("provenance_id")
            if isinstance(provenance_id, str):
                provenance_ids.add(provenance_id)

        return {
            "session_id": self.session.get("session_id"),
            "events": events,
            "assets": assets,
            "provenance": [
                record
                for record in self.provenance
                if record.get("provenance_id") in provenance_ids
            ],
        }


def _asset_ids_for_event(event: JsonObject) -> set[str]:
    payload = event.get("payload", {})
    asset_ids: set[str] = set()
    if isinstance(payload.get("asset_id"), str):
        asset_ids.add(payload["asset_id"])
    if isinstance(payload.get("asset_ids"), list):
        asset_ids.update(item for item in payload["asset_ids"] if isinstance(item, str))
    packet = payload.get("packet")
    if isinstance(packet, dict) and isinstance(packet.get("asset_ref"), str):
        asset_ids.add(packet["asset_ref"])
    for frame in payload.get("frames", []):
        if isinstance(frame, dict) and isinstance(frame.get("asset_ref"), str):
            asset_ids.add(frame["asset_ref"])
    return asset_ids
