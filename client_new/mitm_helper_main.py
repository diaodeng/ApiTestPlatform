import sys


def main():
    from services.mitmproxy_service.helper_process import main as helper_main

    helper_main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
