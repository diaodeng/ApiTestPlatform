from dataclasses import dataclass


@dataclass
class PosChangeState:
    env: str | None = None
    vendor_id: str | None = None
    store_id: str | None = None
    switch_mode: str = "1"

    pos_mac: str = ""
    pos_no: str = ""
    pos_ip: str = ""

    pos_type: str = "1"
    pos_group: str | None = None
