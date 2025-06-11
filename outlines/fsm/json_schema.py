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
    signature = inspect.signature(fn)
    # New: build lists for param names and types at once
    param_items = list(signature.parameters.items())
    param_keys = []
    param_types = []
    for name, arg in param_items:
        if arg.annotation == inspect._empty:
            raise ValueError("Each argument must have a type annotation")
        param_keys.append(name)
        param_types.append(arg.annotation)

    # Try to use __name__, fallback to 'Arguments' if unavailable
    try:
        fn_name = fn.__name__
    except Exception as e:
        fn_name = "Arguments"
        warnings.warn(
            f"The function name could not be determined. Using default name 'Arguments' instead. For debugging, here is exact error:\n{e}",
            category=UserWarning,
        )

    # Use the cached helper
    return _schema_from_signature_cached(fn_name, tuple(param_keys), tuple(param_types))


def get_schema_from_enum(myenum: type[Enum]) -> dict:
    if len(myenum) == 0:
        raise ValueError(
            f"Your enum class {myenum.__name__} has 0 members. If you are working with an enum of functions, do not forget to register them as callable (using `partial` for instance)"
        )
    # Prealloc
    choices = []
    for elt in myenum:
        v = elt.value
        if callable(v):
            # Use the optimized and cached signature->schema
            # If value is a callable with attribute 'func' (partial/lambda), use that
            func = v.func if hasattr(v, "func") else v
            choices.append(get_schema_from_signature(func))
        else:
            choices.append({'const': v})
    return {"title": myenum.__name__, "oneOf": choices}


@lru_cache(maxsize=256)
def _schema_from_signature_cached(qual_name: str, param_keys: tuple, param_types: tuple) -> dict:
    # Helper for the signature-to-schema, uses primitive args for cacheability.
    fields = {name: (tp, ...) for name, tp in zip(param_keys, param_types)}
    model = create_model(qual_name, **fields)
    return model.model_json_schema()
