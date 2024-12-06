
import httpx

def serialize_url(url: httpx.URL):
    """httpx.URL对象转字典"""
    url_property = {
        "host": url.host,
        "path": url.path,
        "scheme": url.scheme,
        "query": url.query.decode("utf-8"),
        "fragment": url.fragment
    }
    return url_property

def serialize_request(request: httpx.Request):
    """httpx.Request对象转字典"""
    request_property = {
        "url": serialize_url(request.url),
        "method": request.method,
        # "headers": request.headers
    }
    return request_property

def serialize_response(response: httpx.Response):
    """httpx.Response对象转字典"""
    response_property = {
        "elapsed": timedelta_to_str(response.elapsed),
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "cookies": dict(response.cookies),
        "text": response.text,
        "json": response.json(),
        "content": response.content.decode('utf-8'),
        "url": serialize_url(response.url),
        "request": serialize_request(response.request),
        "http_version": response.http_version,
        "reason_phrase": response.reason_phrase,
        "encoding": response.encoding,
        "charset_encoding": response.charset_encoding,
        "is_informational": response.is_informational,
        "is_success": response.is_success,
        "is_redirect": response.is_redirect,
        "is_client_error": response.is_client_error,
        "is_server_error": response.is_server_error,
        "is_error": response.is_error,
        "has_redirect_location": response.has_redirect_location,
        "links": dict(response.links),
        "num_bytes_downloaded": response.num_bytes_downloaded
    }
    return response_property

def timedelta_to_str(delta):
    """timedelta转字符串"""
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    microseconds = delta.microseconds // 1000  # 将微秒转换为毫秒（可选）
    return f"{days} days, {hours}:{minutes}:{seconds}.{microseconds}"
