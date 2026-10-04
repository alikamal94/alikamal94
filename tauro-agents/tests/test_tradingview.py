from tauro.data.tradingview import parse_bars


def test_parse_dict_rows():
    bars = parse_bars({"bars": [{"time": 1759550400, "open": 1, "high": 3, "low": 0.5, "close": 2},
                                {"time": 1759536000, "open": 0.9, "high": 1.2, "low": 0.8, "close": 1}]})
    assert [b.close for b in bars] == [1, 2]  # sorted oldest first


def test_parse_arrays_and_columns():
    assert parse_bars([[1759536000000, 1, 2, 0.5, 1.5]])[0].high == 2
    cols = parse_bars({"t": [1759536000], "o": [1], "h": [2], "l": [0.5], "c": [1.5]})
    assert cols[0].low == 0.5
