import json
from httriop import GET, remote, serve, headers, variables


@GET("/", output=json)
async def root(msg):
    print("received:", repr(msg), "from:", remote.get())
    print("headers:", headers.get())
    return {"hello": True}


@GET("/add/<x:int>/<y:int>/", output=json)
async def test(msg):
    print("received:", repr(msg), "from:", remote.get())
    print("headers:", headers.get())
    bindings = variables.get()
    x = bindings["x"]
    y = bindings["y"]
    return {"result": x + y}


@GET(404)
async def notfound(_):
    return "404 Not Found!!"


@GET(400)
async def clienterror(_):
    return "You dumb!"


@GET(504)
async def timeout(_):
    return "too slow!"


if __name__ == "__main__":
    serve()
