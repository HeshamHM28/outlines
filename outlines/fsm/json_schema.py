import inspect
import json
import warnings
from enum import Enum
from functools import lru_cache
from typing import Callable, Type, Union

from pydantic import BaseModel, create_model


def convert_json_schema_to_str(json_schema: Union[dict, str, Type[BaseModel]]) -> str:
    """Convert a JSON schema to a string.

    Parameters
    ----------
    json_schema
        The JSON schema.

    Returns
    -------
    str
        The JSON schema converted to a string.

    Raises
    ------
    ValueError
        If the schema is not a dictionary, a string or a Pydantic class.
    """
    if isinstance(json_schema, dict):
        schema_str = json.dumps(json_schema)
    elif isinstance(json_schema, str):
        schema_str = json_schema
    elif issubclass(json_schema, BaseModel):
        schema_str = json.dumps(json_schema.model_json_schema())
    else:
        raise ValueError(
            f"Cannot parse schema {json_schema}. The schema must be either "
            + "a Pydantic class, a dictionary or a string that contains the JSON "
            + "schema specification"
        )
    return schema_str


def get_schema_from_signature(fn: Callable) -> dict:
    """Turn a function signature into a JSON schema.

    Every JSON object valid to the output JSON Schema can be passed
    to `fn` using the ** unpacking syntax.

    """
    try:
        function_key = get_function_key(fn)
        return _get_schema_from_signature_cached(function_key)
    except Exception as e:
        # try to get fn name for warning
        try:
            fn_name = fn.__name__
        except Exception as inner_e:
            fn_name = "Arguments"
            warnings.warn(
                f"The function name could not be determined. Using default name 'Arguments' instead. Additional error:\n{inner_e}",
                category=UserWarning,
            )
        raise


def get_schema_from_enum(myenum: type[Enum]) -> dict:
    if len(myenum) == 0:
        raise ValueError(
            f"Your enum class {myenum.__name__} has 0 members. If you are working with an enum of functions, do not forget to register them as callable (using `partial` for instance)"
        )
    choices = [
        get_schema_from_signature(elt.value.func)
        if callable(elt.value)
        else {"const": elt.value}
        for elt in myenum
    ]
    schema = {"title": myenum.__name__, "oneOf": choices}
    return schema


def get_function_key(fn: Callable):
    """Return a tuple uniquely identifying a function's schema-relevant info."""
    sig = inspect.signature(fn)
    items = tuple(
        (name, param.annotation)
        for name, param in sig.parameters.items()
    )
    # Adding function name for cache uniqueness, in rare case of different functions with same sig in different modules
    return (fn.__name__, items)

@lru_cache(maxsize=256)
def _get_schema_from_signature_cached(function_key):
    fn_name, params = function_key
    arguments = {}
    for name, type_ in params:
        if type_ == inspect._empty:
            raise ValueError("Each argument must have a type annotation")
        arguments[name] = (type_, ...)
    model = create_model(fn_name, **arguments)
    return model.model_json_schema()
