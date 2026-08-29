from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)
    default_region: str | None = Field(default=None, max_length=100)
    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm: raise ValueError("password and password_confirm must match")
        return self
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; email: EmailStr; default_region: str | None; created_at: datetime
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
