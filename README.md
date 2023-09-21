# `isjsonschemasubset`

Check one JSONSchema is a subset of another. Plays nicely with `Pydantic`.

# Install

```bash
pip install isjsonschemasubset
```

_Currently in an Alpha._

# Usage

```python
from pathlib import Path
from isjsonschemasubset import dump, issubset, load

path_to_a = Path(__file__).parent / "a.json"
path_to_b = Path(__file__).parent / "b.json"
dump(A, path_to_a)  # where A is a `type[pydantic.BaseModel]`
dump(B, path_to_b)  # where B is a `type[pydantic.BaseModel]`
json_schema_a = load(path_to_a)
json_schema_b = load(path_to_b)

for error in issubset(json_schema_a, json_schema_b):
    ...
```

Yields errors if type `A` is not a subset of `B`.

In this context, "is a subset of" means that if we were to do:

```python
B(**a.model_dump(mode="json"))
```

We would _not_ get an error. This is very important when deserializing data from JSON columns in the database and for writing backwards compatible APIs.

See [tests/test_schema_versions.py](tests/test_schema_versions.py) for further example usage. In this case, every time we change `Foo` (or anything that `Foo` refers to recursively), we dump a new schema in [tests/schemas/Foo](tests/schemas/Foo) and check all of the schemas are backwards compatible.


# Dev install

```bash
git clone git@github.com:leontrolski/isjsonschemasubset.git
pip install -r requirements-dev.txt
pytest
mypy src tests --strict
```

## Upload to pypi

```bash
# bump version
python -m pip install build twine
python -m build
twine check dist/*
twine upload dist/*
```
