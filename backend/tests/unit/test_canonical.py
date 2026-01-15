from app.core.canonical import (
    normalize_text,
    canonical_json,
    hash_sha256,
    canonical_hash_from_text,
    canonical_hash_from_json,
)

def test_normalize_text_whitespace_and_nfkc():
    raw = " \tHello\u00A0World\t\n"
    n = normalize_text(raw)
    assert n == "Hello World"
    raw2 = "Cafe\u0301 ☕"
    n2 = normalize_text(raw2)
    assert "é" in n2
    assert isinstance(n2, str)

def test_canonical_json_sorted_keys():
    a = {"b": 1, "a": 2, "list": [3, 2, 1]}
    b = {"list": [3, 2, 1], "a": 2, "b": 1}
    ja = canonical_json(a)
    jb = canonical_json(b)
    assert ja == jb

def test_sha256_and_hashes_determinism():
    s1 = "hello"
    s2 = "hello"
    assert hash_sha256(s1) == hash_sha256(s2)
    obj1 = {"x": 1, "y": 2}
    obj2 = {"y": 2, "x": 1}
    h1 = canonical_hash_from_json(obj1)
    h2 = canonical_hash_from_json(obj2)
    assert h1 == h2

def test_canonical_hash_from_text_is_stable_with_dirty_input():
    t1 = "Hello   World"
    t2 = "Hello\tWorld\n"
    h1 = canonical_hash_from_text(t1)
    h2 = canonical_hash_from_text(t2)
    assert h1 == h2
