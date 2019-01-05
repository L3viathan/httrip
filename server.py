import json
from httriop import GET, remote, serve, headers


@GET("/", output=json)
async def root(msg):
    print("received:", repr(msg), "from:", remote.get())
    print("headers:", headers.get())
    return {"hello": True}


@GET("/test/<foo:int>", output=json)
async def test(msg):
    print("received:", repr(msg), "from:", remote.get())
    print("headers:", headers.get())
    return {"hello": False}


@GET(404)
async def notfound(_):
    return "404 Not Found!!"


@GET(400)
async def clienterror(_):
    return "You dumb!"


@GET(504)
async def timeout(_):
    return "too slow!"


if __name__ == '__main__':
    serve()
