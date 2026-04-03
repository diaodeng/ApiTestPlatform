import fnmatch
import os


class SearchService:
    def search(self, directories, file_pattern="*", callback=None, stop_flag=None):
        results = []

        for d in directories:
            for root, dirs, files in os.walk(d):
                if stop_flag and stop_flag():
                    return results

                for f in files:
                    if fnmatch.fnmatch(f.lower(), file_pattern.lower()):
                        full_path = os.path.join(root, f)
                        results.append(full_path)

                        if callback:
                            callback(full_path)

        return results
