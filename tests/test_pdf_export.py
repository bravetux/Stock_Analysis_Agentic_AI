from src.ui.pdf_export import markdown_to_pdf, save_pdf_to_disk


def test_markdown_to_pdf_returns_bytes():
    md = "# Test Report\n\nThis is a **test** report.\n\n| Col1 | Col2 |\n|------|------|\n| A | B |"
    result = markdown_to_pdf(md, "RELIANCE", "NSE", "beginner")
    assert isinstance(result, bytes)
    assert len(result) > 0
    # PDF magic bytes
    assert result[:5] == b"%PDF-"


def test_markdown_to_pdf_with_empty_content():
    result = markdown_to_pdf("", "AAPL", "NASDAQ", "expert")
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_save_pdf_to_disk(tmp_path):
    md = "# Test\nContent"
    pdf_bytes = markdown_to_pdf(md, "RELIANCE", "NSE", "beginner")
    path = save_pdf_to_disk(pdf_bytes, "RELIANCE", "NSE", reports_dir=str(tmp_path))
    assert path.endswith(".pdf")
    assert "NSE_RELIANCE_" in path
    with open(path, "rb") as f:
        assert f.read()[:5] == b"%PDF-"
