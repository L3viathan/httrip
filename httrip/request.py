import io
from contextvars import ContextVar

req_remote = ContextVar("req_remote")
req_headers = ContextVar("req_headers")
req_body = ContextVar("req_body")

res_headers = ContextVar("res_headers")
res_status = ContextVar("res_status")


class Request:
    """
    This object represents the current request and allows access to various
    properties of it:
        body: Contains the (decoded) body of the request
        headers: Contains a dictionary of key-value header mappings
        remote: Contains a tuple of (IP address, port) of the remote

    Internally, this is a singleton class that simplifies access to various
    context variables.
    """
    for key in ["body", "headers", "remote"]:

        def getter(self, key=key):
            return globals()["req_" + key].get(None)

        def setter(self, value, key=key):
            return globals()["req_" + key].set(value)

        vars()[key] = property(fget=getter, fset=setter)


class Response:
    """
    This object represents the current response and allows access to various
    properties of it:
        body: Contains the (decoded) body of the response
        headers: Contains a dictionary of key-value header mappings
        status: Contains information about the HTTP status that this response
            will send

    Internally, this is a singleton class that simplifies access to various
    context variables.
    """
    for key in ["status", "headers"]:

        def getter(self, key=key):
            return globals()["res_" + key].get(None)

        def setter(self, value, key=key):
            return globals()["res_" + key].set(value)

        vars()[key] = property(fget=getter, fset=setter)

    def build_headers(self):
        """Return the HTTP status line and headers"""
        bytestream = io.BytesIO()
        status = self.status
        bytestream.write(b"HTTP/1.1 ")
        if status is None:
            bytestream.write(b"200 OK\r\n")
        else:
            bytestream.write(str(status.code).encode("utf-8"))
            bytestream.write(b" ")
            bytestream.write(status.msg.encode("utf-8"))
            bytestream.write(b"\r\n")
        headers = self.headers or {}
        for key, value in headers.items():
            bytestream.write(key.encode("utf-8"))
            bytestream.write(b": ")
            bytestream.write(str(value).encode("utf-8"))
            bytestream.write(b"\r\n")
        bytestream.write(b"\r\n")

        return bytestream.getvalue()


request = Request()
response = Response()
