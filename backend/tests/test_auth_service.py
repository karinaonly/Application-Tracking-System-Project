import unittest

from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine

from app.auth.models import User
from app.auth.schemas import PasswordChange, ProfileUpdate
from app.auth.service import AuthService, MIN_PASSWORD_LENGTH


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


if __name__ == "__main__":
    unittest.main()
