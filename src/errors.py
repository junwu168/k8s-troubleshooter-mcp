from typing import ClassVar

from pydantic import BaseModel, JsonValue


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: JsonValue | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    code: ClassVar[str] = "application_error"

    def __init__(self, message: str, details: JsonValue | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.details: JsonValue | None = details

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            error=ErrorDetail(
                code=self.code,
                message=self.message,
                details=self.details,
            )
        )


class K8sClientError(AppError):
    code: ClassVar[str] = "k8s_client_error"


class ConfigError(AppError):
    code: ClassVar[str] = "config_error"
