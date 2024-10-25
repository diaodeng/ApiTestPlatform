
async def scan_keys(redis, pattern):
    cursor = '0'
    keys = []
    while cursor != 0:
        cursor, partial_keys = await redis.scan(cursor=cursor, match=pattern)
        keys.extend(partial_keys)
    return keys