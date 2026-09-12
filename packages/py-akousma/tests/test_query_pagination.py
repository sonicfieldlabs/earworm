import akousma
import pytest


def test_pagination_has_stable_ties_and_filters_before_offset(tmp_path):
    with akousma.AkousmataStore(tmp_path) as store:
        for index in range(57):
            record = akousma.new_akousma(audio={"asset_id": str(index)},
                originating_app="oida" if index < 55 else "germ",
                source_type="recorded", origin="file")
            record["created_at"] = "2026-09-08T00:00:00Z"
            store.put(record)
        pages = [store.query(originating_app="oida", limit=25, offset=offset) for offset in (0, 25, 50)]
        ids = [r["akousma_id"] for page in pages for r in page]
        assert len(ids) == len(set(ids)) == 55
        assert ids == sorted(ids, reverse=True)
        assert [r["akousma_id"] for r in store.query(originating_app="oida", limit=55, oldest_first=True)] == list(reversed(ids))
        assert store.query(originating_app="oida", offset=55) == []
        with pytest.raises(ValueError):
            store.query(offset=-1)
