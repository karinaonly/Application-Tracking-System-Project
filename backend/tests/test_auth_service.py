import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

from app.auth.models import User
from app.auth.schemas import PasswordChange, ProfileUpdate, UserRegister
from app.auth.service import AuthService, MIN_PASSWORD_LENGTH
from app.auth.throttle import LoginThrottle, login_throttle


class AuthServiceProfileTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        self.session = Session(engine)
        self.service = AuthService(self.session)
        self.user = User(email="test@example.com", hashed_password=self.service.hash_password("OldPass123"), full_name="Old Name")
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)

    def tearDown(self):
        self.session.close()

    def test_update_profile_changes_full_name(self):
        updated = self.service.update_profile(self.user, ProfileUpdate(full_name="  New Name  "))
        self.assertEqual(updated.full_name, "New Name")

    def test_change_password_success_and_rehash(self):
        self.service.change_password(self.user, PasswordChange(current_password="OldPass123", new_password="NewPass456"))
        self.assertTrue(self.service.verify_password("NewPass456", self.user.hashed_password))
        self.assertFalse(self.service.verify_password("OldPass123", self.user.hashed_password))

    def test_change_password_rejects_wrong_current(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.change_password(self.user, PasswordChange(current_password="WrongPass", new_password="NewPass456"))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("incorrect", ctx.exception.detail)

    def test_change_password_rejects_short_new(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.change_password(self.user, PasswordChange(current_password="OldPass123", new_password="short"))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn(str(MIN_PASSWORD_LENGTH), ctx.exception.detail)
        # The old password must still work after a rejected change.
        self.assertTrue(self.service.verify_password("OldPass123", self.user.hashed_password))


class AuthServiceRegistrationTests(unittest.TestCase):
    """E3: registration enforces the password policy and can be closed."""

    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        self.session = Session(engine)
        self.service = AuthService(self.session)
        login_throttle.clear()

    def tearDown(self):
        login_throttle.clear()
        self.session.close()

    def test_short_password_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.register(UserRegister(
                email="new@example.com", password="short", full_name="New",
            ))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn(str(MIN_PASSWORD_LENGTH), ctx.exception.detail)
        stored = self.session.exec(
            select(User).where(User.email == "new@example.com")
        ).first()
        self.assertIsNone(stored)

    def test_valid_password_registers(self):
        user = self.service.register(UserRegister(
            email="new@example.com", password="GoodPass123", full_name="New",
        ))
        self.assertTrue(self.service.verify_password("GoodPass123", user.hashed_password))

    def test_registration_can_be_disabled(self):
        with patch("app.auth.service.get_settings") as settings:
            settings.return_value.allow_registration = False
            with self.assertRaises(HTTPException) as ctx:
                self.service.register(UserRegister(
                    email="new@example.com", password="GoodPass123",
                    full_name="New",
                ))
        self.assertEqual(ctx.exception.status_code, 403)


class LoginThrottleTests(unittest.TestCase):
    """E3: repeated failed logins are rate-limited per email + client."""

    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        self.session = Session(engine)
        self.service = AuthService(self.session)
        self.user = User(
            email="test@example.com",
            hashed_password=self.service.hash_password("OldPass123"),
            full_name="Test User",
        )
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)
        login_throttle.clear()

    def tearDown(self):
        login_throttle.clear()
        self.session.close()

    def _fail(self, password="wrong", client="1.2.3.4"):
        with self.assertRaises(HTTPException) as ctx:
            self.service.login("test@example.com", password, client=client)
        return ctx.exception

    def test_five_failures_lock_that_client_out(self):
        for _ in range(5):
            self.assertEqual(self._fail().status_code, 401)

        locked = self._fail(password="OldPass123")
        self.assertEqual(locked.status_code, 429)
        self.assertIn("Retry-After", locked.headers)
        self.assertIn("Too many failed", locked.detail)

    def test_success_resets_the_counter(self):
        for _ in range(4):
            self._fail()
        user = self.service.login("test@example.com", "OldPass123", client="1.2.3.4")
        self.assertEqual(user.id, self.user.id)

        # A fresh run of four failures must not trip the limit.
        for _ in range(4):
            self._fail()
        user = self.service.login("test@example.com", "OldPass123", client="1.2.3.4")
        self.assertEqual(user.id, self.user.id)

    def test_other_clients_are_not_locked_out(self):
        for _ in range(5):
            self._fail()
        user = self.service.login("test@example.com", "OldPass123", client="5.6.7.8")
        self.assertEqual(user.id, self.user.id)

    def test_unknown_email_is_throttled_too(self):
        for _ in range(5):
            with self.assertRaises(HTTPException) as ctx:
                self.service.login("ghost@example.com", "wrong", client="1.2.3.4")
            self.assertEqual(ctx.exception.status_code, 401)

        with self.assertRaises(HTTPException) as ctx:
            self.service.login("ghost@example.com", "wrong", client="1.2.3.4")
        self.assertEqual(ctx.exception.status_code, 429)


class LoginThrottleWindowTests(unittest.TestCase):
    """The window is time-based, not a permanent ban."""

    def test_lock_lifts_after_the_window(self):
        throttle = LoginThrottle(max_failures=2, window_seconds=60)
        throttle.record_failure("k", now=0)
        throttle.record_failure("k", now=1)

        self.assertEqual(throttle.retry_after("k", now=2), 58)
        self.assertEqual(throttle.retry_after("k", now=61), 0)

    def test_clear_resets_everything(self):
        throttle = LoginThrottle(max_failures=1, window_seconds=60)
        throttle.record_failure("k", now=0)
        self.assertGreater(throttle.retry_after("k", now=1), 0)
        throttle.clear()
        self.assertEqual(throttle.retry_after("k", now=1), 0)


if __name__ == "__main__":
    unittest.main()
