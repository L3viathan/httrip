# httrip

**httrip** (pronounced *HT-tree-P*) is a tiny proof-of-concept web framework
utilizing [Trio](https://trio.readthedocs.io) to support parallel requests.

## Requirements

- Python 3.6+
- Trio

No other requirements exist. Although Python 3.7's `contextvars` are used, Trio
automatically backports them.

## Usage

To use httrip, write a Python module that calls `httrip.serve`:

```python
from httrip import serve

if __name__ == '__main__':
    serve(8080)  # listens on port 8080
```

To do anything useful, you probably want to use the decorator `httrip.route`
(or its shorthands `httrip.GET` and `httrip.POST`). As parameters, in addition
to the HTTP verb (unless you use the shorthands), list one or more routes:

```python
from httrip import GET, request

@GET("/", "/hello")
async def root():
    print("received:", request.body, "from:", request.remote)
    print("headers:", request.headers)
    return {"hello": True}
```

As you can see, the `request` object can be used to get properties of the
current request. The request body (`request.body`) gets automatically converted
based on the Content-Type in the request header, or based on an optional
keyword argument `input` in the decorator. The output gets converted and
encoded automatically, too (a dictionary as a return value leading to a JSON
encoded object), again with the ability to adjust the conversion using the
keyword argument `output`. Whenever a string gets returned by an output
function, it is automatically converted to bytes. UTF-8 everywhere.

To do error handling, you can specify numbers as routes:

```python
@GET(404, 400, 504)
async def error():
    return f"{response.status.code} {response.status.msg}"
```

This automatically registers this function to be used as an error handler for
those kinds of HTTP errors. Some HTTP errors get raised automatically in some
situations (like 404 for a missing route), but the can also be raised manually
in a handler, by raising a `httrip.HTTPError`. The special number `-1` is a
catch-all number.

To specify dynamic routes, enclose parts of the route string with angle
brackets:

```python
@GET("/add/<x:int>/<y:int>/")
async def test(x, y):
    if x % 2 == 0:
        raise HTTPError(400, "first argument may not be divisible by 2")
    return {"result": x + y, "headers": request.headers}
```

As you can see, you can also specify a conversion function. Values from dynamic
routes get automatically bound to corresponding arguments of the handler
functions
