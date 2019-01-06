import re
import json
import builtins
from .request import request
from .http import HTTPError


def auto_in(something):
    """Automatically convert data to the proper type:

    1. Empty bytestreams get returned as-is
    2. If a Content-Type is defined, use that for decoding (supported at the
        moment: JSON, plain text)
    3. Otherwise, return bytes.

    Args:
        something (bytes): The raw data
    Returns:
        str/bytes/dict: The decoded data
    """
    if not something:
        return something
    ct = request.headers.get("Content-Type")
    if ct == "application/json":
        return json.loads(something.decode("utf-8"))
    elif ct.startswith("text/"):
        return something.decode("utf-8")
    return something


def auto_out(something):
    """Automatically convert data properly to a string:

    1. Dicts and lists trigger encoding as JSON.
    2. str/bytes get returned as-is
    3. None raises a 204 No Content (which is not an error).
    4. Otherwise, raises a 500 Internal Server Error.

    Args:
        something (Any): The incoming data
    Returns:
        str/bytes: The encoded data
    Raises:
        HTTPError: A 204 if None was given, a 500 if anything unknown was given.
    """
    if isinstance(something, (dict, list)):
        return json.dumps(something)
    elif isinstance(something, (str, bytes)):
        return something
    elif something is None:
        raise HTTPError(204)  # No Content
    else:
        raise HTTPError(500)



REGISTRY = {}


def route(method, *paths, input=auto_in, output=auto_out):
    """Bind one or more paths (and a HTTP verb) to a handler.

    A path can either be a static path, such as "/foo/bar/" or a dynamic path,
    containing angle-bracket areas with optional conversion rules, such as
    "/foo/<bar:int>/<bat>/". This example means that if the path "/foo/34/spam"
    is accessed, the number 34 and the string "spam" will be handed to the
    handler as keyword arguments. A trailing slash is always optional, httrip
    makes no difference between "/foo/" and "/foo".

    Instead of a string, a path can also be an integer. In that case, the
    handler becomes an error handler, which gets called when an HTTPError with
    that error code gets raised. For example, you could bind a handler to the
    path 404, with which you could make a custom Not-Found page.
    The number -1 is special; it is a kind of default error handler (it handles
    all not explicitly handled errors).

    Args:
        method (str): The HTTP verb, usually "GET" or "POST"
        *paths (str/int): A list of routes to bind to (e.g. "/", "/foo/bar")
        input (Callable; optional): A function that decodes the body
        output (Callable; optional): A function that encodes the return value

    Returns:
        function: The actual decorator with which to bind the handler
    """
    paths = [
        path.rstrip("/") if isinstance(path, str) else path for path in paths
    ]

    def decorator(afn):
        nonlocal input, output, paths
        if hasattr(afn, "input"):
            raise ValueError(
                "Handlers can only be decorated once. "
                "To attach it to several paths, give them as additional arguments."
            )
        if input == json:

            def input(value):
                return json.loads(value.decode("utf-8"))

        elif input == str:

            def input(value):
                return value.decode("utf-8")

        if output == json:
            output = json.dumps

        for path in paths:
            if isinstance(path, str):
                bindings = re.findall("<([^/:]+)(?::([^/:]+))?>", path)
                path = re.compile(re.sub("<[^>]+>", "([^/]+)", path) + "$")
            else:
                bindings = []

            REGISTRY[method, path] = (afn, bindings)
        afn.output = output
        afn.input = input
        return afn

    return decorator


def POST(*args, **kwargs):
    """Bind a POST route. For details see httrip.routing.route."""
    return route("POST", *args, **kwargs)


def GET(*args, **kwargs):
    """Bind a GET route. For details see httrip.routing.route."""
    return route("GET", *args, **kwargs)


def get_handler(method, path):
    """Find the handler and path bindings for a given method and path.

    Args:
        method (str): HTTP verb, e.g. "GET"
        path (str/int): The actual path of a request (or a number for error
            handlers)
    Returns:
        async function: The handler with which to handle this request
        dict: The bindings from dynamic paths (e.g {"x": 23} from route
            "/<x:int>/" and path "/23/".
    """
    if isinstance(path, int):
        return REGISTRY.get(("GET", path), REGISTRY["GET", -1])
    path = path.rstrip("/")
    afn = None
    bindings = {}
    for m, p in REGISTRY:
        if m != method or isinstance(p, int):
            continue
        match = p.match(path)
        if not match:
            continue

        afn, variables = REGISTRY[m, p]
        for value, (name, transformation) in zip(match.groups(), variables):
            if transformation:
                try:
                    value = getattr(builtins, transformation)(value)
                except Exception:
                    request.error = HTTPError(400, f"Could Not Convert {name}")
                    break
            bindings[name] = value
        break
    else:
        request.error = HTTPError(404, "No Matching Route")
    return afn, bindings


@GET(-1)
async def error():
    """Handle errors if no custom error handler is defined.

    This function exists such that errors don't cause the server to crash if
    you didn't define your own error handlers. Custom handlers (even custom
    -1-handlers) override this.

    Returns:
        str: An error message
    """
    return f"{request.error.code} {request.error.msg}"
