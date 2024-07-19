import platform


def get_platform() -> dict:
    return {
        "httprunner_version": f"Httprunner None",
        "python_version": "{} {}".format(
            platform.python_implementation(),
            platform.python_version()
        ),
        "platform": platform.platform(),
        "pytest_version": f"pytest None",
    }
