
async def scan_keys(redis, pattern):
    cursor = 0
    keys = []
    while True:
        cursor, partial_keys = await redis.scan(cursor=cursor, match=pattern)
        keys.extend(partial_keys)
        if cursor in (0, "0", b"0"):
            break
    return keys
