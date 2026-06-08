from datetime import datetime
from zoneinfo import ZoneInfo

from src.domain.datetime_utils import parse_mp_datetime, to_art

ART = ZoneInfo("America/Argentina/Buenos_Aires")


class TestToArt:
    def test_converts_mp_offset_to_argentina_local_time(self) -> None:
        mp_dt = datetime.fromisoformat("2026-05-18T21:26:21.000-04:00")

        result = to_art(mp_dt)

        assert result.hour == 22
        assert result.minute == 26
        assert result.utcoffset().total_seconds() == -3 * 3600

    def test_keeps_correct_art_datetime_unchanged(self) -> None:
        art_dt = datetime.fromisoformat("2026-05-18T22:26:21-03:00")

        result = to_art(art_dt)

        assert result == art_dt

    def test_assigns_art_to_naive_datetime(self) -> None:
        naive = datetime(2026, 5, 18, 22, 26, 21)

        result = to_art(naive)

        assert result.tzinfo == ART
        assert result.hour == 22


class TestParseMpDatetime:
    def test_parses_iso_string_and_normalizes_to_art(self) -> None:
        result = parse_mp_datetime("2026-05-18T21:26:21.000-04:00")

        assert result.hour == 22
        assert result.tzinfo == ART
