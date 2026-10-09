from app.config import get_settings


def test_explicit_environment_is_not_overwritten_by_local_dotenv(monkeypatch, tmp_path):
    (tmp_path / '.env').write_text(
        'DATABASE_URL=sqlite:///private.db\nGEMINI_API_KEY=local-value\n', encoding='utf-8'
    )
    monkeypatch.setattr('app.config.PROJECT_ROOT', tmp_path)
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('GEMINI_API_KEY', '')
    settings = get_settings()
    assert settings.database_url == 'sqlite:///:memory:'
    assert settings.gemini_api_key == ''
