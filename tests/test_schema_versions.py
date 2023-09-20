from pathlib import Path

from isjsonschemasubset import JSONSchema, Object, dump, issubset, load, resolve
import pytest
from pydantic import BaseModel


SCHEMAS_DIR = Path(__file__).parent / "schemas"
SCHEMAS_DIR.mkdir(exist_ok=True)
TEST_DIR = SCHEMAS_DIR / "test"
TEST_DIR.mkdir(exist_ok=True)


class Foo(BaseModel):
    a: str


BASE_MODELS = (Foo,)


def cls_to_versions_dir(cls: type[BaseModel]) -> Path:
    return SCHEMAS_DIR / cls.__name__


def version_filename(version: int) -> str:
    return f"{version:04d}.json"


def max_version_in_dir(cls_dir: Path) -> int:
    cls_dir.mkdir(exist_ok=True)
    schema_files = sorted(cls_dir.glob("*.json"))
    if not schema_files:
        return 0
    biggest = schema_files[-1]
    return int(biggest.stem)


@pytest.mark.parametrize("cls", BASE_MODELS, ids=[cls.__name__ for cls in BASE_MODELS])
def test_versions(cls: type[BaseModel]) -> None:
    cls_dir = cls_to_versions_dir(cls)
    max_version = max_version_in_dir(cls_dir)
    previous_schema: Object | None = None
    if max_version > 0:
        previous_schema = load(cls_dir / version_filename(max_version))

    current_schema = JSONSchema(**cls.model_json_schema())
    current_schema_resolved = resolve(current_schema)
    if current_schema_resolved != previous_schema:
        dump(cls, cls_dir / version_filename(max_version + 1))

    schema_files = sorted(cls_dir.glob("*.json"))
    for a, b in zip(schema_files, schema_files[1:]):
        all_errors = "\n\n".join(str(e) for e in issubset(load(a), load(b)))
        if all_errors:
            pytest.fail(
                f"Backwards compatible schema failure between {a} and {b}:\n{all_errors}"
            )
