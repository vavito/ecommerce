from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .exceptions import AppException
from .schemas import ErrorResponse


async def app_exception_handler(
    _request: Request,
    exc: AppException,
) -> JSONResponse:
    error_response = ErrorResponse(
        code=exc.code, message=exc.message, details=exc.details or {}
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_response),
    )


async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:

    error_response = ErrorResponse(
        code="VALIDATION_ERROR",
        message="Dados de entrada invalidos.",
        details={"errors": exc.errors()},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder(error_response),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        AppException,
        app_exception_handler,
    )

    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
