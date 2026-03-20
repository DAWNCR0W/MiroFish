import time

from app.utils.file_parser import FileParser


def test_extract_texts_parallel_preserves_input_order(monkeypatch):
    delays = {
        "a.txt": 0.3,
        "b.txt": 0.1,
        "c.txt": 0.2,
    }

    def fake_extract_text(cls, file_path):
        time.sleep(delays[file_path])
        return f"text:{file_path}"

    monkeypatch.setattr(FileParser, "extract_text", classmethod(fake_extract_text))

    start = time.perf_counter()
    texts = FileParser.extract_texts_parallel(
        ["a.txt", "b.txt", "c.txt"],
        max_workers=3,
    )
    elapsed = time.perf_counter() - start

    assert texts == [
        "text:a.txt",
        "text:b.txt",
        "text:c.txt",
    ]
    assert elapsed < 0.5
