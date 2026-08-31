"""Static script validation tests (P5-005, MAJOR-004)."""

from app.services.ai.agents.script_assembler import render_skeleton, validate_script

VALID_STEPS = [
    ("打开登录页", 'page.goto(f"{BASE_URL}/demo/?qaMode={QA_MODE}")'),
    ("输入用户名", 'page.get_by_test_id("username").fill("testuser")'),
    ("点击登录", 'page.get_by_test_id("login-btn").click()'),
    ("校验成功", 'expect(page.get_by_test_id("flash")).to_contain_text("登录成功")'),
]


def _script(steps):
    return render_skeleton(steps, "http://localhost:8001", "none")


def test_valid_script_passes():
    assert validate_script(_script(VALID_STEPS), VALID_STEPS) == []


def test_syntax_error_detected():
    steps = [("坏步骤", 'page.get_by_test_id("x").click("')]  # unterminated string
    errors = validate_script(_script(steps), steps)
    assert any("语法错误" in e or "单表达式" in e for e in errors)


def test_forbidden_sleep_detected():
    steps = VALID_STEPS[:1] + [("等", "page.wait_for_timeout(1000)")] + VALID_STEPS[1:]
    errors = validate_script(_script(steps), steps)
    assert any("wait_for_timeout" in e for e in errors)


def test_hardcoded_url_detected():
    steps = VALID_STEPS[:1] + [("硬编码", 'page.goto("http://example.com")')] + VALID_STEPS[1:]
    errors = validate_script(_script(steps), steps)
    assert any("http://" in e for e in errors)


def test_last_step_must_assert():
    steps = [
        ("a", 'page.get_by_test_id("x").click()'),
        ("b", 'page.get_by_test_id("y").fill("1")'),
        ("c", 'page.get_by_test_id("z").click()'),
    ]
    errors = validate_script(_script(steps), steps)
    assert any("末步" in e for e in errors)


def test_first_step_must_goto():
    # C-3: a script that never navigates cannot "empty pass".
    steps = [
        ("点击", 'page.get_by_test_id("x").click()'),
        ("校验", 'expect(page.get_by_test_id("y")).to_contain_text("ok")'),
    ]
    errors = validate_script(_script(steps), steps)
    assert any("首步" in e for e in errors)


def test_to_have_url_trailing_slash_detected():
    # P016 5-5: exact URL assert must not end with a trailing slash.
    steps = [
        ("打开", 'page.goto(BASE_URL)'),
        ("校验", 'expect(page).to_have_url("https://www.saucedemo.com/")'),
    ]
    errors = validate_script(_script(steps), steps)
    assert any("to_have_url" in e for e in errors)


def test_get_by_text_generic_detected():
    # P016 5-5: a generic get_by_text is flagged.
    steps = [
        ("打开", 'page.goto(BASE_URL)'),
        ("点击", 'page.get_by_text("登录").click()'),
        ("校验", 'expect(page).to_have_url(BASE_URL)'),
    ]
    errors = validate_script(_script(steps), steps)
    assert any("get_by_text" in e for e in errors)


def test_import_whitelist():
    script = "import os\nSTEPS = []\n"
    errors = validate_script(script, [])
    assert any("import" in e for e in errors)


def test_render_skeleton_injects_base_url_and_qa_mode():
    text = render_skeleton(VALID_STEPS, "http://localhost:8001", "selector-change")
    assert 'BASE_URL = "http://localhost:8001"' in text
    assert 'QA_MODE = "selector-change"' in text
    assert 'from playwright.sync_api import Page, expect' in text
