from httriop import request, output_json, REMOTE, serve


@request(output=output_json)
async def handler(msg):
    print("received:", repr(msg), "from:", REMOTE.get())
    return {"hello": True}


if __name__ == '__main__':
    serve(handler)
