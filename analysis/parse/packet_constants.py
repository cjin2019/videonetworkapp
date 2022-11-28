from enum import Enum, IntEnum
from typing import Type

class ZoomMediaWrapper(IntEnum):
    RTP_VIDEO = 16
    RTP_AUDIO = 15
    RTP_SCREEN_SHARE = 13
    RTCP_SENDER_REPORT = 33
    KEEP_ALIVE = 21
    # UNKNOWN = 31
    INVALID = -1

class RTPWrapper(IntEnum):
    VIDEO = 98
    FEC = 110
    UNKNOWN = 0

class ExceptionCodes(Enum):
    INVALID_RTP_VERSION = "Invalid RTP Version"
    FU_A_NOT_RESERVED = "FU-A Not Reserved"

def contains_value(cls: Type[IntEnum] , val: int):
    return val in cls.__members__.values()