from httriop import GET, output_json, REMOTE, serve, HEADERS


@GET("/", output=output_json)
async def handler(msg):
    print("received:", repr(msg), "from:", REMOTE.get())
    print("headers:", HEADERS.get())
    return {"hello": True}


@GET(404)
async def handler(msg):
    return "404 Not Found!!"


if __name__ == '__main__':
    serve()
