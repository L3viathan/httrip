import io
import http
from .state import response


class HTTPError(Exception):
    """Generic HTTP status code.

    The name is slightly misleading, as it doesn't have to represent an error.
    One can, for example, also raise an HTTPError(204) (No Content).

    The msg is optional, and will be set to the canonical one if omitted.
    """
    def __init__(self, code, msg=None):
        self.code = code
        self.msg = (
            msg
            if msg is not None
            else http.HTTPStatus(code).name.replace("_", " ").title()
        )


class Headers(dict):
    def __getitem__(self, item):
        return super().__getitem__(item.lower())
    def __setitem__(self, item, value):
        super().__setitem__(item.lower(), value)


def parse_headers(value):
    """Parse HTTP headers.

    Args:
        value (bytes): The raw HTTP headers, without the trailing CRLFCRLF.

    Returns:
        tuple:
            str: The method or HTTP verb (e.g. "GET")
            str: The path (e.g. "/" or "/index.html")
            dict: The key-value bindings of the HTTP headers
                (e.g. {"Content-Type": "application/json", ...})

    Raises:
        ValueError: If the headers are corrupted (can't find key-value pairs).
    """
    headers = value.decode("utf-8").split("\r\n")
    metaheader = headers.pop(0)
    method, path, _ = metaheader.split()
    try:
        headers = Headers({
            key: value
            for key, value in (
                line.split(": ", maxsplit=1) for line in headers
            )
        })
    except ValueError:
        path = 400
        response.status = HTTPError(400, "Headers Corrupt")
        headers = Headers()
    return method, path, headers



async def get_data(conn):
    """ Given an asynchronous connection, return slightly interpreted data.

    Args:
        conn (trio.SocketStream): The connection from which to retrieve data.

    Returns:
        tuple:
            str: The method or HTTP verb (e.g. "GET")
            str: The path (e.g. "/" or "/index.html")
            dict: The key-value bindings of the HTTP headers
                (e.g. {"Content-Type": "application/json", ...})
            bytes: The body of the HTTP message
    """

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
        response.status = HTTPError(411)  # Length Required

    return method, path, headers, rest
