import csv
from itertools import cycle

class CSVDataSource:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        self.iter = cycle(self.rows)

    def next(self):
        return next(self.iter)
