from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
import json

router = APIRouter()

CLASH_FILE = "clash_admin/data/clashes.json"

@router.get("/yacd")
def yacd_entry(clash: str):
    with open(CLASH_FILE) as f:
        clashes = json.load(f)

    if clash not in clashes:
        raise HTTPException(404, "Clash not found")

    c = clashes[clash]

    with open("clash_admin/yacd/dist/index.html", encoding="utf-8") as f:
        html = f.read()

    inject = f"""
<script>
(function() {{
  localStorage.setItem('clash_config', JSON.stringify({{
    controller: '/clash-admin/clash/{clash}',
    secret: '{c["secret"]}',
    version: 'auto'
  }}));
}})();
</script>
"""

    html = html.replace("<head>", "<head>" + inject)
    return HTMLResponse(html)
