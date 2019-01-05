import io
import builtins
import json
import re
import http
from contextvars import ContextVar
import trio


class HTTPError(Exception):
    def __init__(self, code, msg=None):
        self.code = code
        self.msg = (
            msg if msg is not None else http.HTTPStatus(code).name.title()
        )


class Request:
    @property
    def body(self):
        return cv_body.get()

    @property
    def headers(self):
        return cv_headers.get()

    @property
    def remote(self):
        return cv_remote.get()

    @property
    def error(self):
        return cv_error.get()


request = Request()


def identity(something):
    return something


def parse_headers(value):
    headers_, _, rest = value.partition("\r\n\r\n")
    headers_ = headers_.split("\r\n")
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
        cv_error.set(HTTPError(400, "Headers Corrupt"))
        headers_ = {}
    return method, path, headers_, rest


cv_remote = ContextVar("cv_remote")
cv_headers = ContextVar("cv_headers")
cv_body = ContextVar("cv_body")
cv_error = ContextVar("cv_error")

REGISTRY = {}


def route(method, *paths, input=identity, output=identity):
    paths = [
        path.rstrip("/") if isinstance(path, str) else path for path in paths
    ]

    def decorator(afn):
        nonlocal input, output, paths
        if hasattr(afn, "input"):
            raise ValueError(
                "Handlers can only be decorated once. To attach it to several paths, give them as additional arguments."
            )
        if input == json:
            input = json.loads
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


def GET(*args, **kwargs):
    return route("GET", *args, **kwargs)


@GET(400, 404, 504)
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

        afn, vars = REGISTRY[m, p]
        for value, (name, transformation) in zip(match.groups(), vars):
            if transformation:
                try:
                    value = getattr(builtins, transformation)(value)
                except Exception as e:
                    cv_error.set(HTTPError(400, f"Could Not Convert {name}"))
                    break
            bindings[name] = value
        break
    else:
        # afn, _, input, output = REGISTRY[method, 404]
        cv_error.set(HTTPError(404, "No Matching Route"))
    return afn, bindings


async def get_bytes(conn):
    bytestream = io.BytesIO()
    new = b""
    while not new.endswith(b"\r\n"):
        new = await conn.receive_some(1024)
        bytestream.write(new)
    return bytestream.getvalue().decode("utf-8")


async def handler(conn):
    r_ip, r_port, *_ = conn.socket.getpeername()
    value = await get_bytes(conn)
    method, path, headers_, data = parse_headers(value)
    afn, bindings = get_handler(method, path)

    cv_remote.set((r_ip, r_port))
    cv_headers.set(headers_)
    try:
        cv_body.set(afn.input(data))
    except AttributeError:
        pass  # will be handled later
    except ValueError:
        cv_error.set(HTTPError(400, "Failed To Convert Input Data"))

    result = ""
    with trio.move_on_after(15):
        try:
            exc = cv_error.get(None)
            if exc:
                raise exc
            with trio.fail_after(10):
                result = afn.output(await afn(**bindings))
        except trio.TooSlowError:
            afn, bindings = REGISTRY["GET", 504]
            cv_error.set(HTTPError(504, "Task Timed Out"))
            result = afn.output(await afn())
        except HTTPError as e:
            afn, bindings = REGISTRY["GET", e.code]
            cv_error.set(e)
            result = afn.output(await afn())
    await conn.send_all(result.encode("utf-8"))


async def main(port):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.serve_tcp, handler, port)


def serve(port):
    try:
        trio.run(main, port)
    except KeyboardInterrupt:
        pass
