import aiohttp
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
from config import config


class Proxy6Type(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class Proxy6Country(str, Enum):
    RU = "ru"
    US = "us"
    DE = "de"
    NL = "nl"
    GB = "gb"
    FR = "fr"
    CA = "ca"
    # Add more as needed


@dataclass
class Proxy6Proxy:
    id: str
    ip: str
    port: int
    user: Optional[str]
    password: Optional[str]
    type: str
    country: str
    city: Optional[str]
    isp: Optional[str]
    date_end: str  # ISO format
    price: float


@dataclass
class Proxy6Balance:
    balance: float
    currency: str


@dataclass
class Proxy6Pricing:
    period_days: int
    price_per_proxy: float
    count: int


class Proxy6APIError(Exception):
    def __init__(self, message: str, code: int = 0):
        self.message = message
        self.code = code
        super().__init__(f"Proxy6 API Error {code}: {message}")


class Proxy6Client:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or config.PROXY6_API_KEY
        self.base_url = (base_url or config.PROXY6_API_URL).rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to Proxy6 API"""
        session = await self._get_session()
        params["apikey"] = self.api_key

        url = f"{self.base_url}/{method}"
        async with session.get(url, params=params) as resp:
            data = await resp.json()

        if data.get("status") != "yes":
            raise Proxy6APIError(
                data.get("error", "Unknown error"),
                data.get("error_code", 0)
            )

        return data

    # --- Balance ---

    async def get_balance(self) -> Proxy6Balance:
        """Get account balance"""
        data = await self._request("getbalance", {})
        return Proxy6Balance(
            balance=float(data.get("balance", 0)),
            currency=data.get("currency", "RUB")
        )

    # --- Get Proxies ---

    async def get_proxies(self, state: str = "active") -> List[Proxy6Proxy]:
        """Get list of proxies"""
        data = await self._request("getproxy", {"state": state})
        proxies = []
        for item in data.get("list", {}).values():
            proxies.append(Proxy6Proxy(
                id=str(item.get("id")),
                ip=item.get("ip"),
                port=int(item.get("port")),
                user=item.get("user"),
                password=item.get("pass"),
                type=item.get("type"),
                country=item.get("country"),
                city=item.get("city"),
                isp=item.get("isp"),
                date_end=item.get("date_end"),
                price=float(item.get("price", 0)),
            ))
        return proxies

    async def get_proxy_by_id(self, proxy_id: str) -> Optional[Proxy6Proxy]:
        """Get single proxy by ID"""
        data = await self._request("getproxy", {"ids": proxy_id})
        items = data.get("list", {})
        if proxy_id in items:
            item = items[proxy_id]
            return Proxy6Proxy(
                id=str(item.get("id")),
                ip=item.get("ip"),
                port=int(item.get("port")),
                user=item.get("user"),
                password=item.get("pass"),
                type=item.get("type"),
                country=item.get("country"),
                city=item.get("city"),
                isp=item.get("isp"),
                date_end=item.get("date_end"),
                price=float(item.get("price", 0)),
            )
        return None

    # --- Buy Proxies ---

    async def get_pricing(
        self,
        proxy_type: Proxy6Type,
        country: Proxy6Country,
        period_days: int = 30,
        count: int = 1,
        version: int = 4,
    ) -> Proxy6Pricing:
        """Get pricing for proxies"""
        data = await self._request("getprices", {
            "type": proxy_type.value,
            "country": country.value,
            "period": period_days,
            "count": count,
            "version": version,
        })
        return Proxy6Pricing(
            period_days=period_days,
            price_per_proxy=float(data.get("price", 0)),
            count=count,
        )

    async def buy_proxies(
        self,
        proxy_type: Proxy6Type,
        country: Proxy6Country,
        period_days: int = 30,
        count: int = 1,
        version: int = 4,
        auto_renewal: bool = False,
    ) -> List[Proxy6Proxy]:
        """Buy new proxies"""
        data = await self._request("buy", {
            "type": proxy_type.value,
            "country": country.value,
            "period": period_days,
            "count": count,
            "version": version,
            "auto_renewal": "true" if auto_renewal else "false",
        })

        proxies = []
        for item in data.get("list", {}).values():
            proxies.append(Proxy6Proxy(
                id=str(item.get("id")),
                ip=item.get("ip"),
                port=int(item.get("port")),
                user=item.get("user"),
                password=item.get("pass"),
                type=item.get("type"),
                country=item.get("country"),
                city=item.get("city"),
                isp=item.get("isp"),
                date_end=item.get("date_end"),
                price=float(item.get("price", 0)),
            ))
        return proxies

    # --- Manage Proxies ---

    async def prolong_proxy(self, proxy_id: str, period_days: int) -> bool:
        """Extend proxy rental period"""
        data = await self._request("prolong", {
            "ids": proxy_id,
            "period": period_days,
        })
        return data.get("status") == "yes"

    async def delete_proxy(self, proxy_id: str) -> bool:
        """Delete/return proxy"""
        data = await self._request("delete", {"ids": proxy_id})
        return data.get("status") == "yes"

    async def set_auto_renewal(self, proxy_id: str, enabled: bool) -> bool:
        """Set auto-renewal for proxy"""
        data = await self._request("setauto", {
            "ids": proxy_id,
            "auto_renewal": "true" if enabled else "false",
        })
        return data.get("status") == "yes"

    async def change_ip(self, proxy_id: str) -> Optional[Proxy6Proxy]:
        """Change proxy IP (if supported)"""
        data = await self._request("changeip", {"ids": proxy_id})
        items = data.get("list", {})
        if proxy_id in items:
            item = items[proxy_id]
            return Proxy6Proxy(
                id=str(item.get("id")),
                ip=item.get("ip"),
                port=int(item.get("port")),
                user=item.get("user"),
                password=item.get("pass"),
                type=item.get("type"),
                country=item.get("country"),
                city=item.get("city"),
                isp=item.get("isp"),
                date_end=item.get("date_end"),
                price=float(item.get("price", 0)),
            )
        return None

    # --- Countries and Types ---

    async def get_countries(self, proxy_type: Proxy6Type) -> Dict[str, str]:
        """Get available countries for proxy type"""
        data = await self._request("getcountries", {"type": proxy_type.value})
        return data.get("list", {})

    async def get_types(self) -> Dict[str, str]:
        """Get available proxy types"""
        data = await self._request("gettypes", {})
        return data.get("list", {})


# Singleton instance
proxy6_client = Proxy6Client()


# Helper functions for bot integration
async def buy_proxies_for_user(
    proxy_type: str,
    country: str,
    count: int,
    period_days: int = 30,
) -> List[Proxy6Proxy]:
    """High-level function to buy proxies for user"""
    return await proxy6_client.buy_proxies(
        proxy_type=Proxy6Type(proxy_type),
        country=Proxy6Country(country),
        count=count,
        period_days=period_days,
    )


async def get_proxy_price(
    proxy_type: str,
    country: str,
    count: int,
    period_days: int = 30,
) -> float:
    """Get total price for proxies"""
    pricing = await proxy6_client.get_pricing(
        proxy_type=Proxy6Type(proxy_type),
        country=Proxy6Country(country),
        count=count,
        period_days=period_days,
    )
    return pricing.price_per_proxy * count


async def get_available_countries(proxy_type: str) -> Dict[str, str]:
    """Get available countries for proxy type"""
    return await proxy6_client.get_countries(Proxy6Type(proxy_type))