from contextvars import ContextVar

cv_remote = ContextVar("cv_remote")
cv_headers = ContextVar("cv_headers")
cv_body = ContextVar("cv_body")
cv_error = ContextVar("cv_error")


class Request:
    """
    This object represents the current request and allows access to various
    properties of it:
        body: Contains the (decoded) body of the request
        headers: Contains a dictionary of key-value header mappings
        remote: Contains a tuple of (IP address, port) of the remote
        error: Contains information about the HTTP error that this request
            caused (or None)

    Internally, this is a singleton class that simplifies access to various
    context variables.
    """
    for key in ["body", "headers", "remote", "error"]:

        def getter(self, key=key):
            return globals()["cv_" + key].get(None)

        def setter(self, value, key=key):
            return globals()["cv_" + key].set(value)

        vars()[key] = property(fget=getter, fset=setter)


request = Request()
