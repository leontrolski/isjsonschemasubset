import datetime as dt
import enum
from pathlib import Path

from isjsonschemasubset import Object, dump, issubset, load
from pydantic import BaseModel


SCHEMAS_DIR = Path(__file__).parent / "schemas"
SCHEMAS_DIR.mkdir(exist_ok=True)
TEST_DIR = SCHEMAS_DIR / "test"
TEST_DIR.mkdir(exist_ok=True)


class StrOnly(BaseModel):
    a: str


class StrOrNone(BaseModel):
    a: str | None


class IntOnly(BaseModel):
    a: int


class IntOrStr(BaseModel):
    a: int | str


class DateOnly(BaseModel):
    a: dt.date


class DateTimeOnly(BaseModel):
    a: dt.datetime


class StrNested(BaseModel):
    b: StrOnly


class IntNested(BaseModel):
    b: IntOnly


class StrOrNoneNested(BaseModel):
    b: StrOrNone | None


class IntOrStrNested(BaseModel):
    b: IntOrStr | None


class StrNoDefault(BaseModel):
    a: str
    b: float


class StrAndDefault(BaseModel):
    a: str
    b: float | None = None


class AB(enum.Enum):
    a = "a"
    b = "b"


class ABC(enum.Enum):
    a = "a"
    b = "b"
    c = "c"


class BC(enum.Enum):
    b = "b"
    c = "c"


class EnumAB(BaseModel):
    choices: AB


class EnumABC(BaseModel):
    choices: ABC


class EnumBC(BaseModel):
    choices: BC


class X(BaseModel):
    a: str


class Y(BaseModel):
    a: int


class Z(BaseModel):
    a: float


class UnionXY(BaseModel):
    choices: X | Y


class UnionXYZ(BaseModel):
    choices: X | Y | Z


class UnionYZ(BaseModel):
    choices: Y | Z


def schema(cls: type[BaseModel]) -> Object:
    cls_name = cls.__name__
    p = TEST_DIR / f"{cls_name}.json"
    dump(cls, p)
    return load(p)


def test_basic() -> None:
    actual = [str(e) for e in issubset(schema(StrOnly), schema(StrOnly))]
    expected: list[str] = []
    assert actual == expected


def test_basic_errors() -> None:
    actual = [str(e) for e in issubset(schema(StrOnly), schema(IntOnly))]
    expected = ["At .a Types don't match - a: String b: Integer"]
    assert actual == expected


def test_date_errors() -> None:
    actual = [str(e) for e in issubset(schema(DateOnly), schema(DateTimeOnly))]
    expected = ["At .a String formats do not match - a: String b: String"]
    assert actual == expected


def test_or_none() -> None:
    actual = [str(e) for e in issubset(schema(StrOnly), schema(StrOrNone))]
    expected: list[str] = []
    assert actual == expected


def test_or_none_errors() -> None:
    actual = [str(e) for e in issubset(schema(StrOrNone), schema(StrOnly))]
    expected = ["At .a Types don't match - a: Null b: String"]
    assert actual == expected


def test_nested() -> None:
    actual = [str(e) for e in issubset(schema(StrNested), schema(StrNested))]
    expected: list[str] = []
    assert actual == expected


def test_nested_errors() -> None:
    actual = [str(e) for e in issubset(schema(StrNested), schema(IntNested))]
    expected = ["At .b.a Types don't match - a: String b: Integer"]
    assert actual == expected


def test_nested_union_errors() -> None:
    actual = [str(e) for e in issubset(schema(StrOrNoneNested), schema(IntOrStrNested))]
    expected = [
        "At .b.a Types don't match - a: Null b: Integer",
        "At .b.a Types don't match - a: Null b: String",
        "At .b Types don't match - a: Object b: Null",
    ]
    assert actual == expected


def test_missing_key() -> None:
    actual = [str(e) for e in issubset(schema(StrOnly), schema(StrNoDefault))]
    expected = ["At .b Key: b not in a - a: Object b: Object"]
    assert actual == expected


def test_missing_key_with_default() -> None:
    actual = [str(e) for e in issubset(schema(StrOnly), schema(StrAndDefault))]
    expected: list[str] = []
    assert actual == expected


def test_enum() -> None:
    actual = [str(e) for e in issubset(schema(EnumAB), schema(EnumAB))]
    expected: list[str] = []
    assert actual == expected


def test_enum_subset() -> None:
    actual = [str(e) for e in issubset(schema(EnumAB), schema(EnumABC))]
    expected: list[str] = []
    assert actual == expected


def test_enum_superset() -> None:
    actual = [str(e) for e in issubset(schema(EnumABC), schema(EnumAB))]
    expected = ["At .choices Following keys not in a: c - a: String b: String"]
    assert actual == expected


def test_enum_intersection() -> None:
    actual = [str(e) for e in issubset(schema(EnumAB), schema(EnumBC))]
    expected = ["At .choices Following keys not in a: a - a: String b: String"]
    assert actual == expected


def test_union_subset() -> None:
    actual = [str(e) for e in issubset(schema(UnionXY), schema(UnionXYZ))]
    expected: list[str] = []
    assert actual == expected


def test_union_superset() -> None:
    actual = [str(e) for e in issubset(schema(UnionXYZ), schema(UnionXY))]
    expected = [
        "At .choices.a Types don't match - a: Number b: String",
        "At .choices.a Types don't match - a: Number b: Integer",
    ]
    assert actual == expected


def test_union_intersection() -> None:
    actual = [str(e) for e in issubset(schema(UnionXY), schema(UnionYZ))]
    expected = [
        "At .choices.a Types don't match - a: String b: Integer",
        "At .choices.a Types don't match - a: String b: Number",
    ]
    assert actual == expected
