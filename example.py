from httrip import GET, POST, serve, request, HTTPError


@GET("/")
async def root():
    print("received:", request.body, "from:", request.remote)
    print("headers:", request.headers)
    return {"hello": True}


@GET("/nope")
async def nope():
    raise HTTPError(404)


@GET("/add/<x:int>/<y:int>/")
async def test(x, y):
    if x % 2 == 0:
        raise HTTPError(400, "first argument may not be divisible by 2")
    return {"result": x + y, "headers": request.headers}


@GET(404, 400, 504)
async def error():
    return f"{request.error.code} {request.error.msg}"


@POST("/")
async def posttest():
    return {"foo": "bar"}


if __name__ == "__main__":
    serve(8080)
