from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class Rect(BaseModel):
    x: int
    y: int
    w: int
    h: int


class CodeSlide(BaseModel):
    type: Literal["code"]
    voice: str
    language: str
    active_file: str
    file_tree: list[str]
    code: str


class ImageSlide(BaseModel):
    type: Literal["image"]
    voice: str
    src: str
    rect: Rect | None = None
    transition: Literal["fade", "lerp_rect"] = "fade"


Slide = Annotated[Union[CodeSlide, ImageSlide], Field(discriminator="type")]
