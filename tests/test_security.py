from security import SecurityConfig


def test_generated_secrets_are_unique_and_long():
    a, b = SecurityConfig.generate_secrets(), SecurityConfig.generate_secrets()
    assert set(a) == {"SECRET_KEY", "JWT_SECRET", "CSRF_TOKEN_SECRET"}
    for key in a:
        assert len(a[key]) >= 32
        assert a[key] != b[key]


def test_env_template_has_placeholders_only():
    tpl = SecurityConfig.create_env_template()
    assert "SECRET_KEY=YOUR_SECRET_KEY_HERE" in tpl
    assert "DEBUG=False" in tpl
