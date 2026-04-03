from server.config import SearchConfig
from utils.file_handle import search_files


class ScanService:
    @staticmethod
    def scan():
        config = SearchConfig.read()

        result = []

        for d in config.dir:
            files = search_files(
                directory=d, target_file=config.file_pattern, use_wildcard=True
            )
            result.extend(files)

        SearchConfig.save_search_result(result)
        return result
