import io
import builtins
import json
import re
import http
import trio
from .request import request


class HTTPError(Exception):
    def __init__(self, code, msg=None):
        self.code = code
        self.msg = (
            msg
            if msg is not None
            else http.HTTPStatus(code).name.replace("_", " ").title()
        )


def auto_in(something):
    if not something:
        return something
    ct = request.headers.get("Content-Type")
    if ct == "application/json":
        return json.loads(something.decode("utf-8"))
    elif ct.startswith("text/"):
        return something.decode("utf-8")
    return something


def auto_out(something):
    if isinstance(something, (dict, list)):
        return json.dumps(something)
    elif isinstance(something, (str, bytes)):
        return something
    elif something is None:
        raise HTTPError(204)  # No Content
    else:
        raise HTTPError(500)


def parse_headers(value):
    headers_ = value.decode("utf-8").split("\r\n")
    metaheader = headers_.pop(0)
    method, path, _ = metaheader.split()
    try:
        headers_ = {
            key: value
            for key, value in (
                line.split(": ", maxsplit=1) for line in headers_
            )
        }
    except ValueError:
        path = 400
        request.error = HTTPError(400, "Headers Corrupt")
        headers_ = {}
    return method, path, headers_


REGISTRY = {}


def route(method, *paths, input=auto_in, output=auto_out):
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
    return route("POST", *args, **kwargs)


def GET(*args, **kwargs):
    return route("GET", *args, **kwargs)


@GET(-1)
async def error():
    return f"{request.error.code} {request.error.msg}"


def get_handler(method, path):
    path = path.rstrip("/") if isinstance(path, str) else path
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


async def get_data(conn):
    bytestream = io.BytesIO()
    new = b""
    while b"\r\n\r\n" not in new:
        new = await conn.receive_some(1024)
        bytestream.write(new)
    headers, _, rest = bytestream.getvalue().partition(b"\r\n\r\n")
    method, path, headers = parse_headers(headers)
    cl = int(headers.get("Content-Length", 0))
    if cl:
        size = len(rest)
        bytestream = io.BytesIO()
        bytestream.write(rest)
        while size < cl:
            new = await conn.receive_some(cl - size)
            bytestream.write(new)
            size += len(new)
        rest = bytestream.getvalue()
    elif rest:
        request.error = HTTPError(411)  # Length Required

    return method, path, headers, rest


def to_bytes(value):
    if isinstance(value, str):
        return value.encode("utf-8")
    elif isinstance(value, bytes):
        return value
    else:
        raise ValueError("Return value must be bytes")


async def handler(conn):
    r_ip, r_port, *_ = conn.socket.getpeername()
    method, path, headers_, data = await get_data(conn)
    afn, bindings = get_handler(method, path)

    request.remote = (r_ip, r_port)
    request.headers = headers_
    try:
        request.body = afn.input(data)
    except AttributeError:
        pass  # will be handled later
    except ValueError:
        request.error = HTTPError(400, "Failed To Convert Input Data")

    result = ""
    with trio.move_on_after(15):
        try:
            exc = request.error
            if exc:
                raise exc
            with trio.fail_after(10):
                result = afn.output(await afn(**bindings))
        except trio.TooSlowError:
            afn, bindings = REGISTRY["GET", 504]
            request.error = HTTPError(504, "Task Timed Out")
            result = afn.output(await afn())
        except HTTPError as e:
            afn, bindings = REGISTRY.get(("GET", e.code), REGISTRY["GET", -1])
            request.error = e
            result = afn.output(await afn())
    await conn.send_all(to_bytes(result))


async def main(port):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.serve_tcp, handler, port)


def serve(port):
    try:
        trio.run(main, port)
    except KeyboardInterrupt:
        pass
