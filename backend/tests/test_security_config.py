import unittest

from app.config.settings import Settings, validate_security_settings


def make_settings(**overrides) -> Settings:
    return Settings(**overrides)


class ValidateSecuritySettingsTests(unittest.TestCase):
    def test_valid_secret_passes(self):
        settings = make_settings(jwt_secret="s" * 32)
        validate_security_settings(settings)

    def test_missing_secret_fails(self):
        with self.assertRaises(RuntimeError) as ctx:
            validate_security_settings(make_settings(jwt_secret=""))
        self.assertIn("JWT_SECRET", str(ctx.exception))

    def test_short_secret_fails(self):
        with self.assertRaises(RuntimeError) as ctx:
            validate_security_settings(make_settings(jwt_secret="s" * 31))
        self.assertIn("too short", str(ctx.exception))

    def test_old_insecure_default_is_gone(self):
        # The old hardcoded value must never be a valid default again.
        settings = make_settings()
        self.assertNotEqual(settings.jwt_secret, "local-secret-key")


class CorsOriginListTests(unittest.TestCase):
    def test_default_origins_exclude_wildcard(self):
        settings = make_settings()
        origins = settings.cors_origin_list
        self.assertNotIn("*", origins)
        self.assertIn("http://localhost:8443", origins)

    def test_origins_are_parsed_from_comma_list(self):
        settings = make_settings(cors_origins="http://a.test, http://b.test ,")
        self.assertEqual(settings.cors_origin_list, ["http://a.test", "http://b.test"])


class DatabaseEchoTests(unittest.TestCase):
    def test_echo_defaults_to_off(self):
        settings = make_settings()
        self.assertFalse(settings.db_echo)


if __name__ == "__main__":
    unittest.main()
