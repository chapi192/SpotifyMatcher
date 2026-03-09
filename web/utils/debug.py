from web.config import DEBUG_BUILD

def build_debug(msg):
    if DEBUG_BUILD:
        print("[BUILD DEBUG]", msg)