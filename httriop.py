import io
import json
from contextvars import ContextVar
import trio


def identity(something):
    return something


def parse_headers(value):
    headers_, _, rest = value.partition("\r\n\r\n")
    headers_ = headers_.split("\r\n")
    metaheader = headers_.pop(0)
    method, path, _ = metaheader.split()
    headers_ = {
        key: value
        for key, value in (line.split(": ", maxsplit=1) for line in headers_)
    }
    return method, path, headers_, rest


remote = ContextVar("remote")
headers = ContextVar("headers")

REGISTRY = {}


def request(method, path, input=identity, output=identity):
    def decorator(afn):
        nonlocal input, output
        if input == json:
            input = json.loads
        if output == json:
            output = json.dumps

        REGISTRY[method, path] = (afn, input, output)
        return afn

    return decorator


def GET(*args, **kwargs):
    return request("GET", *args, **kwargs)


def get_handler(method, path):
    if (method, path) not in REGISTRY:
        path = 404

    # TODO: magical handling of "/foo/<bar:int>" etc

    return REGISTRY[method, path]


async def handler(conn):
    bytestream = io.BytesIO()
    r_ip, r_port, *_ = conn.socket.getpeername()
    new = b""
    while not new.endswith(b"\r\n"):
        new = await conn.receive_some(1024)
        bytestream.write(new)
    value = bytestream.getvalue().decode("utf-8")
    method, path, headers_, data = parse_headers(value)
    remote.set((r_ip, r_port))
    headers.set(headers_)

    afn, input, output = get_handler(method, path)
    result = await afn(input(data))
    await conn.send_all(output(result).encode("utf-8"))


async def main():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.serve_tcp, handler, 8080)


def serve():
    trio.run(main)
