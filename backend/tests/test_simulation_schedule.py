from app.utils.simulation_schedule import normalize_active_hours


def test_normalize_active_hours_parses_time_range_string():
    assert normalize_active_hours("09:00-17:00", default=[8, 9]) == list(range(9, 18))


def test_normalize_active_hours_parses_json_string_list():
    assert normalize_active_hours("[9, 10, 11]") == [9, 10, 11]


def test_normalize_active_hours_falls_back_for_none():
    assert normalize_active_hours(None, default=[8, 9, 10]) == [8, 9, 10]


def test_normalize_active_hours_extracts_hours_from_comma_string():
    assert normalize_active_hours("18, 19, 20, 21") == [18, 19, 20, 21]
