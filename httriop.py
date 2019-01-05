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


def request(input=identity, output=identity):
    def decorator(afn):
        async def inner(conn):
            bytestream = io.BytesIO()
            r_ip, r_port, *_ = conn.socket.getpeername()
            new = b""
            while not new.endswith(b"\r\n"):
                new = await conn.receive_some(1024)
                bytestream.write(new)
            value = bytestream.getvalue().decode("utf-8")
            REMOTE.set((r_ip, r_port))
            path, headers, data = parse_headers(value)
            result = await afn(input(value))
            await conn.send_all(output(result).encode("utf-8"))

        return inner

    return decorator


def output_json(value):
    return json.dumps(value)


def input_json(value):
    return json.loads(value)


async def main(handler):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.serve_tcp, handler, 8080)


def serve(handler):
    trio.run(main, handler)
