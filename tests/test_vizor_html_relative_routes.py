from synlynk.viz import generate_board_html


def test_board_html_uses_relative_api_routes():
    html = generate_board_html(8721)

    assert "fetch('api/board" in html or 'fetch("api/board' in html
    assert "fetch('api/board/status'" in html or 'fetch("api/board/status"' in html
    assert "fetch('api/board/stage'" in html or 'fetch("api/board/stage"' in html
    assert "fetch('/api/board" not in html
    assert "fetch('/api/board/status'" not in html
    assert "fetch('/api/board/stage'" not in html
