from synlynk import native_capture as nc
from tests.native_capture_fixtures import assistant, pr_link


def test_repeated_message_id_counts_once_first_seen_wins():
    data = "\n".join([assistant("m1", o=5), assistant("m1", o=5), assistant("m2", o=7)]).encode() + b"\n"
    res = nc.parse_chunk(data, known_ids=set())
    assert [r.message_id for r in res.records] == ["m1", "m2"]
    assert res.consumed == len(data)


def test_dedup_against_ids_known_from_earlier_chunks_at_any_distance():
    known = {f"x{i}" for i in range(1000)}   # session-wide, not a sliding window
    data = (assistant("x0") + "\n" + assistant("m2") + "\n").encode()
    res = nc.parse_chunk(data, known_ids=known)
    assert [r.message_id for r in res.records] == ["m2"]
    assert known == {f"x{i}" for i in range(1000)}   # parse_chunk does not mutate its input


def test_incomplete_trailing_line_is_left_unconsumed():
    complete = (assistant("m1") + "\n").encode()
    partial = b'{"type":"assistant","message":{"id":"m2"'
    res = nc.parse_chunk(complete + partial, known_ids=set())
    assert res.consumed == len(complete)
    assert len(res.records) == 1


def test_synthetic_model_and_non_assistant_skipped():
    data = (assistant("m1", model="<synthetic>") + "\n" + pr_link(5) + "\n").encode()
    res = nc.parse_chunk(data, known_ids=set())
    assert res.records == []
    assert res.pr_links == [(5, "2026-11-24T10:05:00.000Z")]


def test_format_drift_fails_loudly():
    bad = '{"type":"assistant","timestamp":"2026-11-24T10:00:00Z","message":{"id":"m1","model":"x","usage":{"tokens":5}}}\n'
    try:
        nc.parse_chunk(bad.encode(), known_ids=set())
        raised = False
    except nc.TranscriptFormatError:
        raised = True
    assert raised


def test_buckets_split_by_model_and_utc_day():
    lines = [assistant("m1", ts="2026-11-24T23:59:00.000Z"),
             assistant("m2", ts="2026-11-25T00:01:00.000Z"),
             assistant("m3", model="claude-opus-4-8", ts="2026-11-25T00:02:00.000Z")]
    res = nc.parse_chunk(("\n".join(lines) + "\n").encode(), known_ids=set())
    b = nc.bucketize(res.records)
    assert set(b) == {("claude-sonnet-5-5", "2026-11-24"), ("claude-sonnet-5-5", "2026-11-25"), ("claude-opus-4-8", "2026-11-25")}
    assert b[("claude-sonnet-5-5", "2026-11-24")].output_tokens == 20
