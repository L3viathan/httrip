import json
from httriop import GET, remote, serve, headers


@GET("/", output=json)
async def handler(msg):
    print("received:", repr(msg), "from:", remote.get())
    print("headers:", headers.get())
    return {"hello": True}


@GET(404)
async def handler(_):
    return "404 Not Found!!"


if __name__ == '__main__':
    serve()
