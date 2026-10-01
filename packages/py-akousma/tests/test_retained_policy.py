from akousma.retained_policy import retained_covenant, blocks_untyped_prose


def test_policy_locations_are_cumulative_not_overrides():
    record = {"covenant": {"rules_applied": ["do_not_reveal:speech"]},
              "extensions": {"oida.native-policy": {"covenant": {"id": "new-name"}}},
              "listening": {"one": {"payload": {"listening_context": {"covenant": {"rules_applied": []}}}}}}
    assert blocks_untyped_prose(retained_covenant(record))
    assert record["covenant"]["rules_applied"] == ["do_not_reveal:speech"]


def test_restricted_consent_is_a_prose_boundary():
    assert blocks_untyped_prose(retained_covenant({"provenance": {"consent_status": "restricted"}}))
    assert not blocks_untyped_prose(retained_covenant({}))
