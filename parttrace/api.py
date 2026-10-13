"""Required HTTP contracts; all catalogue calculations stay in the engine."""

from contextlib import asynccontextmanager
from pathlib import Path
import re
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .catalogue import Catalogue, DEFAULT_DATA, PartNotFound


class Contract(BaseModel):
    # Reject accidental fields or coerced types rather than silently changing
    # the required response contract when the engine is edited in the future.
    model_config = ConfigDict(extra="forbid", strict=True)


class ValidationResponse(Contract):
    parts: int = Field(ge=0)
    ready: int = Field(ge=0)
    missing: int = Field(ge=0)
    not_replaceable: int = Field(ge=0)


class ChildResponse(Contract):
    part_number: str
    quantity: int = Field(gt=0)


class PartResponse(Contract):
    part_number: str
    description: str | None
    revision: str | None
    status: Literal["ready", "missing", "not_replaceable"]
    total_quantity: int = Field(gt=0)
    parents: list[str]
    children: list[ChildResponse]


class PathsResponse(Contract):
    part_number: str
    paths: list[list[str]]


class SerialResponse(Contract):
    serial: int = Field(ge=0)
    applicable_parts: int = Field(ge=0)


class HealthResponse(Contract):
    status: Literal["ok"]


def get_catalogue(request: Request) -> Catalogue:
    catalogue = getattr(request.app.state, "catalogue", None)
    if catalogue is None:
        raise HTTPException(status_code=503, detail="Catalogue is not ready")
    return catalogue


LoadedCatalogue = Annotated[Catalogue, Depends(get_catalogue)]


def parse_serial(serial: str) -> int:
    if not re.fullmatch(r"[0-9]+", serial):
        raise HTTPException(status_code=422, detail="Serial must contain only ASCII digits (0-9)")
    try:
        return int(serial)
    except ValueError:
        raise HTTPException(status_code=422, detail="Serial exceeds supported integer parsing limits") from None


def create_app(data_directory: str | Path = DEFAULT_DATA, *, root: str = "AS-40000") -> FastAPI:
    """An isolated app per dataset; the normal service always uses root data/."""
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.catalogue = None
        # Construction either succeeds completely or aborts startup. Uvicorn
        # does not accept HTTP traffic until this lifespan reaches yield.
        catalogue = Catalogue.from_directory(data_directory, root=root)
        application.state.catalogue = catalogue
        try:
            yield
        finally:
            application.state.catalogue = None

    application = FastAPI(
        title="PartTrace API", version="0.1.0", lifespan=lifespan,
        # Built-in interactive docs use CDN assets. Keep the JSON schema local;
        # the demo page uses only assets served by this same process.
        docs_url=None, redoc_url=None,
    )
    application.state.catalogue = None
    static = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=static), name="static")

    @application.get("/", include_in_schema=False)
    def demo():
        return FileResponse(static / "index.html", headers={
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            "Cache-Control": "no-cache",
        })

    @application.exception_handler(PartNotFound)
    async def part_not_found(request: Request, error: PartNotFound):
        return JSONResponse(status_code=404, content={"detail": "Part not found in machine"})

    @application.get("/health", response_model=HealthResponse)
    def health(catalogue: LoadedCatalogue):
        return {"status": "ok"}

    @application.get("/api/validation", response_model=ValidationResponse)
    def validation(catalogue: LoadedCatalogue):
        return catalogue.validation()

    @application.get("/api/parts/{part_number}", response_model=PartResponse)
    def part(part_number: str, catalogue: LoadedCatalogue):
        return catalogue.part(part_number)

    @application.get("/api/parts/{part_number}/paths", response_model=PathsResponse)
    def paths(part_number: str, catalogue: LoadedCatalogue):
        return catalogue.paths(part_number)

    @application.get("/api/serial/{serial}", response_model=SerialResponse)
    def serial_match(serial: str, catalogue: LoadedCatalogue):
        # Explicit syntax avoids framework-dependent float/integer coercion.
        return catalogue.serial(parse_serial(serial))

    # Optional demo data is deliberately separate from the required /api contracts.
    @application.get("/demo/search")
    def search(catalogue: LoadedCatalogue, q: str = ""):
        return catalogue.search(q)

    @application.get("/demo/quality")
    def quality(catalogue: LoadedCatalogue):
        return catalogue.quality()

    @application.get("/demo/parts/{part_number}/explanation")
    def explanation(part_number: str, catalogue: LoadedCatalogue, serial: str | None = None):
        return catalogue.explain(part_number, parse_serial(serial) if serial is not None else None)

    return application


app = create_app()
