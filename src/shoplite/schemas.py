import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value: str) -> str:
        email = value.strip().lower()
        if not email or not EMAIL_RE.match(email):
            raise ValueError("email is invalid")
        return email

    @field_validator("password")
    @classmethod
    def password_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("password is required")
        return value.strip()


class CartItemRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1, le=10)
