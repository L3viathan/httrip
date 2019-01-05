import json
from httriop import GET, serve, request, HTTPError


@GET("/", output=json)
async def root():
    print("received:", request.body, "from:", request.remote)
    print("headers:", request.headers)
    return {"hello": True}


@GET("/add/<x:int>/<y:int>/", output=json)
async def test(x, y):
    if x % 2 == 0:
        raise HTTPError(400, "first argument may not be divisible by 2")
    return {"result": x + y, "headers": request.headers}


@GET(404, 400, 504)
async def error():
    return f"{request.error.code} {request.error.msg}"


if __name__ == "__main__":
    serve(8080)
