from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=2)
    email: EmailStr
    name: str = Field(min_length=2)
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    remember: bool = False

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class SwitchTenantRequest(BaseModel):
    tenant_id: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    tenant_id: str
    tenant_name: str
    currency: str = "USD"
    is_email_verified: bool
    is_onboarding_complete: bool
    is_platform_admin: bool = False


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class AuthResponse(BaseModel):
    data: TokenData
    message: str


class MessageResponse(BaseModel):
    message: str


class SwitchTenantData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: str
    tenant_name: str
    role: str
    currency: str = "USD"
    is_onboarding_complete: bool


class SwitchTenantResponse(BaseModel):
    data: SwitchTenantData
    message: str


class ValidateTokenData(BaseModel):
    user_id: str
    email: str
    role: str
    tenant_id: str
    exp: int


class ValidateTokenResponse(BaseModel):
    data: ValidateTokenData


class MFAChallengeResponse(BaseModel):
    mfa_required: bool = True
    challenge_token: str
    mfa_methods: list[str] = ["totp"]


class MFAVerifyRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=8)


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()
