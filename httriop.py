import io
import builtins
import json
import re
from contextvars import ContextVar
import trio


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
    except Exception:
        path = 400
        headers_ = {}
    return method, path, headers_, rest


remote = ContextVar("remote")
headers = ContextVar("headers")
variables = ContextVar("variables")

REGISTRY = {}


def request(method, path, input=identity, output=identity):
    path = path.rstrip("/") if isinstance(path, str) else path

    def decorator(afn):
        nonlocal input, output, path
        if input == json:
            input = json.loads
        if output == json:
            output = json.dumps

        if isinstance(path, str):
            vars = re.findall("<([^/:]+)(?::([^/:]+))?>", path)
            path = re.compile(re.sub("<[^>]+>", "([^/]+)", path) + "$")
        else:
            vars = []

        REGISTRY[method, path] = (afn, vars, input, output)
        return afn

    return decorator


def GET(*args, **kwargs):
    return request("GET", *args, **kwargs)


@GET
async def notfound(_):
    return "404 Not Found"


@GET
async def clienterror(_):
    return "400 Client Error"


@GET
async def timeout(_):
    return "504 Gateway Timeout"


def get_handler(method, path):
    path = path.rstrip("/") if isinstance(path, str) else path
    bindings = {}
    for m, p in REGISTRY:
        if m != method or isinstance(p, int) or not p.match(path):
            continue
        match = p.findall(path)

        afn, vars, input, output = REGISTRY[m, p]
        for value, (name, transformation) in zip(match, vars):
            if transformation:
                try:
                    value = getattr(builtins, transformation)(value)
                except Exception:
                    afn, _, input, output = REGISTRY[method, 400]
                    break
            bindings[name] = value
        variables.set(bindings)
        break
    else:
        afn, _, input, output = REGISTRY[method, 404]
    return afn, bindings, input, output


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
    afn, vars, input, output = get_handler(method, path)

    remote.set((r_ip, r_port))
    headers.set(headers_)
    variables.set(vars)

    result = ""
    with trio.move_on_after(15):
        try:
            with trio.fail_after(10):
                result = output(await afn(input(data)))
        except trio.TooSlowError:
            afn, vars, input, output = REGISTRY["GET", 504]
            result = output(await afn(input(data)))
    await conn.send_all(result.encode("utf-8"))


async def main():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.serve_tcp, handler, 8080)


def serve():
    trio.run(main)
