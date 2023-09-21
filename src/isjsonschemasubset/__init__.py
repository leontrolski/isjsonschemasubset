from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterator, Literal as L, assert_never, overload

import pydantic


# TODO: check the JSONSchema meta and fill in the blanks


class Base(pydantic.BaseModel):
    title: str = ""
    description: str = ""


class Null(Base):
    type: L["null"]


class Boolean(Base):
    type: L["boolean"]
    default: bool | None = None


class Integer(Base):
    type: L["integer"]
    enum: list[int] | None = None
    default: int | None = None


class Number(Base):
    type: L["number"]
    enum: list[float] | None = None
    default: float | None = None


class String(Base):
    type: L["string"]
    enum: list[str] | None = None
    format: str | None = None
    default: str | None = None


class Array(Base):
    type: L["array"]
    items: "Value"


class Object(Base):
    type: L["object"]
    properties: dict[str, "Value"] = pydantic.Field(default_factory=dict)
    required: list[str] = pydantic.Field(default_factory=list)


class AllOf(Base):
    all_of: list["Value"] = pydantic.Field(
        ...,
        validation_alias=pydantic.AliasChoices("allOf", "all_of"),
        serialization_alias="allOf",
    )
    default: None | bool | int | float | str = None


class AnyOf(Base):
    any_of: list["Value"] = pydantic.Field(
        ...,
        validation_alias=pydantic.AliasChoices("anyOf", "any_of"),
        serialization_alias="anyOf",
    )
    default: None | bool | int | float | str = None


class Ref(Base):
    ref: str = pydantic.Field(
        ...,
        validation_alias=pydantic.AliasChoices("$ref", "ref"),
        serialization_alias="$ref",
    )


Value = Null | Boolean | Integer | Number | String | Array | Object | AllOf | AnyOf | Ref


class JSONSchema(pydantic.BaseModel):
    type: L["object"]
    title: str
    definitions: dict[str, Value] = pydantic.Field(
        default_factory=dict,
        validation_alias=pydantic.AliasChoices("$defs", "definitions"),
        serialization_alias="$defs",
    )
    properties: dict[str, Value] = pydantic.Field(default_factory=dict)
    required: list[str] = pydantic.Field(default_factory=list)


def dump(cls: type[pydantic.BaseModel], p: Path) -> None:
    s = json.dumps(cls.model_json_schema(), sort_keys=True, indent=4)
    p.write_text(s)


@overload
def resolve(o: JSONSchema) -> Object:
    ...


@overload
def resolve(o: Value, definitions: dict[str, Value]) -> Value:
    ...


def resolve(o: JSONSchema | Value, definitions: dict[str, Value] | None = None) -> Value:
    """Recursively inline the definitions from the JSONSchema."""
    if definitions is None:
        assert isinstance(o, JSONSchema)
        definitions = o.definitions

    if isinstance(o, JSONSchema):
        return Object(
            type="object",
            properties={k: resolve(v, definitions) for k, v in o.properties.items()},
            required=o.required,
        )
    if isinstance(o, (Null, Boolean, Integer, Number, String)):
        return o
    if isinstance(o, Array):
        return Array(type="array", items=resolve(o.items, definitions))
    if isinstance(o, Object):
        properties = None
        if o.properties is not None:
            properties = {k: resolve(v, definitions) for k, v in o.properties.items()}
        return Object(
            type="object",
            properties=properties,
            required=o.required,
        )
    if isinstance(o, AllOf):
        if len(o.all_of) != 1 or not isinstance(o.all_of[0], Ref):
            raise NotImplementedError("Only support AllOf poiting to one reference")
        _, __, name = o.all_of[0].ref.split("/")
        v = definitions[name]
        if o.default is not None:
            v.default = o.default
        return v
    if isinstance(o, AllOf):
        raise NotImplementedError("Only support AllOf poiting to one reference")
    if isinstance(o, AnyOf):
        return AnyOf(
            any_of=[resolve(v, definitions) for v in o.any_of],
            default=o.default,
        )
    if isinstance(o, Ref):
        _, __, name = o.ref.split("/")
        return resolve(definitions[name], definitions)

    assert_never(o)


@dataclass
class Error:
    path: tuple[str, ...]
    a: Value
    b: Value
    msg: str = "Types don't match"

    def __str__(self) -> str:
        return (
            f"At .{'.'.join(self.path)} {self.msg} - "
            f"a: {self.a.__class__.__name__} b: {self.b.__class__.__name__}"
        )


def issubset(a: Value, b: Value, path: tuple[str, ...] = ()) -> Iterator[Error]:
    """Yield errors if the type `a` is not a subset of `b`.

    In this context, "is a subset of" means that for the corresponding
    Pydantic models, if we were to do:

        b(**a.model_dump(mode="json"))

    We would not get an error. This is very important when parsing data
    from JSON columns in the database.
    """
    if isinstance(a, AnyOf):  # if any options have any errors
        for a_value in a.any_of:
            yield from issubset(a_value, b, path)
    elif isinstance(b, AnyOf):  # if all options have any errors
        all_errors = [list(issubset(a, b_value, path)) for b_value in b.any_of]
        if all(errors for errors in all_errors):
            for errors in all_errors:
                yield from iter(errors)
    elif isinstance(a, String):
        if not isinstance(b, String):
            yield Error(path, a, b)
        elif a.format != b.format:
            yield Error(path, a, b, "String formats do not match")
        elif b.enum is not None:
            if a.enum is None:
                yield Error(path, a, b, "Cannot fit any string into an Enum")
            elif set(a.enum) - set(b.enum):
                keys_in_a_not_b = ", ".join(set(a.enum) - set(b.enum))
                yield Error(path, a, b, f"Following keys not in a: {keys_in_a_not_b}")
    elif isinstance(a, (Null, Boolean, Integer, Number)):
        if type(a) != type(b):
            yield Error(path, a, b)
    elif isinstance(a, Array):
        if not isinstance(b, Array):
            yield Error(path, a, b)
        else:
            yield from issubset(a.items, b.items, path + ("[]",))
    elif isinstance(a, Object):
        if not isinstance(b, Object):
            yield Error(path, a, b)
        else:
            for b_key, b_value in b.properties.items():
                if b_key in b.required and b_key not in a.properties:
                    yield Error(
                        path + (b_key,),
                        a,
                        b,
                        f"Key: {b_key} not in {', '.join(a.properties)}",
                    )
                if b_key in a.properties:
                    a_value = a.properties[b_key]
                    yield from issubset(a_value, b_value, path + (b_key,))
    else:
        yield Error(path, a, b, "Unknown type")


def load(p: Path) -> Object:
    schema = JSONSchema(**json.loads(p.read_bytes()))
    return resolve(schema)
