import trio
from .request import request
from .http import get_data, HTTPError
from .routing import get_handler


def to_bytes(value):
    """Turn strings into bytes, and leave bytes as-is.

    Args:
        value (Any): Some kind of data
    Returns:
        bytes: The data converted to bytes if it was bytes or str.
    Raises:
        ValueError: If the data was some other type.
    """
    if isinstance(value, str):
        return value.encode("utf-8")
    elif isinstance(value, bytes):
        return value
    else:
        raise ValueError("Return value must be bytes")


async def handler(conn):
    """
    Handle an incoming connection.
    This asynchronous function retrieves the request coming from an incoming
    connection, figures out which specific handler it belongs to, converts the
    body according to specified rules (or automatically), awaits the handler,
    and sends the result (properly encoded) back to the remote.

    Args:
        conn (trio.SocketStream): The asynchronous connection.
    """
    r_ip, r_port, *_ = conn.socket.getpeername()
    method, path, headers, data = await get_data(conn)
    afn, bindings = get_handler(method, path)

    request.remote = (r_ip, r_port)
    request.headers = headers
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
            afn, bindings = get_handler("GET", 504)
            request.error = HTTPError(504, "Task Timed Out")
            result = afn.output(await afn())
        except HTTPError as e:
            afn, bindings = get_handler("GET", e.code)
            request.error = e
            result = afn.output(await afn())
    await conn.send_all(to_bytes(result))


async def main(port):
    """Listen on a given port and start handler tasks for incoming connections.

    Args:
        port (int): The port to listen on.
    """
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.serve_tcp, handler, port)


def serve(port):
    """Start the web server and listen for new connections indefinitely.

    Args:
        port (int): The port to listen on.
    """
    try:
        trio.run(main, port)
    except KeyboardInterrupt:
        pass
