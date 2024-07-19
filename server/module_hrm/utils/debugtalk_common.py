import json
import urllib.parse
import requests


def get_host_from_url(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.port:
        return f"{parsed_url.hostname}:{parsed_url.port}"
    else:
        return parsed_url.hostname



__all__ = ["get_host_from_url"]
