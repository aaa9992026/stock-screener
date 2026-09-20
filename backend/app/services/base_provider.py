from abc import ABC, abstractmethod


class BaseMarketDataProvider(ABC):

    @abstractmethod
    def get_companies(self):
        pass

    @abstractmethod
    def get_ohlcv(self, symbol: str, start_date=None, end_date=None):
        pass