import io
import json
from contextvars import ContextVar
import trio


def identity(something):
    return something


def parse_headers(value):
    headers, _, rest = value.partition("\r\n\r\n")
    headers = headers.split("\r\n")
    metaheader = headers.pop(0)
    headers = {
        key: value
        for key, value in (line.split(": ", maxsplit=1) for line in headers)
    }
    return metaheader.split()[1], headers, rest


REMOTE = ContextVar("REMOTE")
HEADERS = ContextVar("HEADERS")

REGISTRY = {}


def request(path, input=identity, output=identity):
    def decorator(afn):
        REGISTRY[path] = (afn, input, output)
        return afn
    return decorator



async def handler(conn):
    bytestream = io.BytesIO()
    r_ip, r_port, *_ = conn.socket.getpeername()
    new = b""
    while not new.endswith(b"\r\n"):
        new = await conn.receive_some(1024)
        bytestream.write(new)
    value = bytestream.getvalue().decode("utf-8")
    path, headers, data = parse_headers(value)
    REMOTE.set((r_ip, r_port))
    HEADERS.set(headers)

    afn, input, output = REGISTRY[path]
    result = await afn(input(data))
    await conn.send_all(output(result).encode("utf-8"))


def output_json(value):
    return json.dumps(value)


def input_json(value):
    return json.loads(value)


async def main():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.serve_tcp, handler, 8080)


def serve():
    trio.run(main)
