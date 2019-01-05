import json
from httriop import GET, serve, request


@GET("/", output=json)
async def root():
    print("received:", request.body, "from:", request.remote)
    print("headers:", request.headers)
    return {"hello": True}


@GET("/add/<x:int>/<y:int>/", output=json)
async def test(x, y):
    return {"result": x + y}


@GET(404)
async def notfound():
    return "404 Not Found!!"


@GET(400)
async def clienterror():
    return "You dumb!"


@GET(504)
async def timeout():
    return "too slow!"


if __name__ == "__main__":
    serve()
