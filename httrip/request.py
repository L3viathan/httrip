from contextvars import ContextVar

cv_remote = ContextVar("cv_remote")
cv_headers = ContextVar("cv_headers")
cv_body = ContextVar("cv_body")
cv_error = ContextVar("cv_error")


class Request:
    for key in ["body", "headers", "remote", "error"]:

        def getter(self, key=key):
            return globals()["cv_" + key].get(None)

        def setter(self, value, key=key):
            return globals()["cv_" + key].set(value)

        vars()[key] = property(fget=getter, fset=setter)


request = Request()
