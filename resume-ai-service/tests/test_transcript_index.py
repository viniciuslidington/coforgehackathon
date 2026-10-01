from __future__ import annotations

from app.core.vtt import Caption
from app.services import database, transcript_index
from app.services.transcript_index import MAX_CHUNK_WORDS, chunk_captions, index_meeting


def _captions(count: int, words: int = 20) -> list[Caption]:
    return [
        Caption(
            start=f"00:{index // 60:02d}:{index % 60:02d}.000",
            end=f"00:{index // 60:02d}:{index % 60:02d}.900",
            text=f"Speaker{index % 2}: " + " ".join(f"w{index}" for _ in range(words)),
        )
        for index in range(count)
    ]


def test_chunks_never_split_a_caption_and_respect_the_word_limit() -> None:
    captions = _captions(30)
    chunks = chunk_captions(captions)

    texts = {caption.text for caption in captions}
    for chunk in chunks:
        lines = chunk.text.split("\n")
        assert all(line in texts for line in lines)
        assert len(chunk.text.split()) <= MAX_CHUNK_WORDS
    # Every caption lands in at least one chunk.
    assert texts <= {line for chunk in chunks for line in chunk.text.split("\n")}


def test_chunk_bounds_are_real_cue_bounds() -> None:
    captions = _captions(12)
    starts = {caption.start for caption in captions}
    ends = {caption.end for caption in captions}

    for chunk in chunk_captions(captions):
        assert chunk.start in starts
        assert chunk.end in ends
        assert chunk.transcript.startswith(f"[{chunk.start}–")


def test_neighbouring_chunks_share_one_caption() -> None:
    chunks = chunk_captions(_captions(12))

    assert chunks[0].text.split("\n")[-1] == chunks[1].text.split("\n")[0]


def test_a_caption_longer_than_the_limit_is_a_chunk_on_its_own() -> None:
    long_caption = _captions(1, words=MAX_CHUNK_WORDS + 40)
    chunks = chunk_captions(_captions(2) + [
        Caption(start="00:05:00.000", end="00:05:30.000", text=long_caption[0].text),
    ])

    assert chunks[-1].text == long_caption[0].text


def test_chunks_record_their_speakers() -> None:
    (chunk,) = chunk_captions(_captions(2, words=5))

    assert chunk.speakers == ["Speaker0", "Speaker1"]


def test_reindexing_is_idempotent(db_path, fake_embedder) -> None:
    captions = _captions(20)
    first = index_meeting("m1", captions)
    second = index_meeting("m1", captions)

    assert first == second
    assert database.chunk_index_stamp()[0] == first


def test_a_chunker_version_bump_marks_meetings_for_reindexing(db_path, fake_embedder, monkeypatch) -> None:
    index_meeting("m1", _captions(5))
    assert transcript_index.is_indexed("m1")

    monkeypatch.setattr(transcript_index, "CHUNKER_VERSION", "chunks-v999")

    assert not transcript_index.is_indexed("m1")
    assert database.indexed_meeting_ids("chunks-v999") == set()


def test_ensure_scope_indexed_is_bounded_and_reports_what_is_left(db_path, fake_embedder, monkeypatch) -> None:
    fetched: list[str] = []

    def captions_for(meeting_id: str) -> list[Caption]:
        fetched.append(meeting_id)
        return _captions(3)

    monkeypatch.setattr(transcript_index.transcript_repository, "get_captions", captions_for)

    left = transcript_index.ensure_scope_indexed(["a", "b", "c"], budget=2)

    assert fetched == ["a", "b"]
    assert left == ["c"]


def test_deleting_a_meeting_removes_its_chunks(db_path, fake_embedder) -> None:
    database.upsert_summary(
        meeting_id="m1", title="t", meeting_date="2026-09-01", participants=[],
        simple_summary="s", keywords=[], duration_seconds=1,
    )
    index_meeting("m1", _captions(5))

    database.delete_summary("m1")

    assert database.chunk_index_stamp()[0] == 0
    assert database.fts_search('"w1"', ["m1"], 10) == []
