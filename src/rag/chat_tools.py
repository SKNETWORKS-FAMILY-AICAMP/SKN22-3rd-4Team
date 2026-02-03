"""
AnalystChatbot에서 사용하는 도구(Tool) 정의 및 스키마 관리
"""


def get_chat_tools():
    """챗봇이 사용할 수 있는 도구 목록 반환"""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_stock_quote",
                "description": "Get real-time stock price (c), change (d), percent change (dp), high (h), low (l).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Company ticker symbol (e.g. AAPL)",
                        }
                    },
                    "required": ["ticker"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_company_profile",
                "description": "Get company profile (industry, market cap, IPO date, etc).",
                "parameters": {
                    "type": "object",
                    "properties": {"ticker": {"type": "string"}},
                    "required": ["ticker"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_price_target",
                "description": "Get analyst price target and consensus.",
                "parameters": {
                    "type": "object",
                    "properties": {"ticker": {"type": "string"}},
                    "required": ["ticker"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_company_news",
                "description": "Get recent company news.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "from_date": {
                            "type": "string",
                            "description": "YYYY-MM-DD",
                        },
                        "to": {"type": "string", "description": "YYYY-MM-DD"},
                    },
                    "required": ["ticker"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_market_news",
                "description": "Get general market news.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["general", "forex", "crypto", "merger"],
                            "default": "general",
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "register_company",
                "description": "Register a new company to the database if the user asks to add/register it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "The company ticker symbol to register.",
                        }
                    },
                    "required": ["ticker"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_exchange_rate",
                "description": "Get current exchange rate between currencies. Default is USD to KRW. Use this when user asks about exchange rates, currency conversion, or wants to know stock prices in KRW (Korean Won).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_currency": {
                            "type": "string",
                            "description": "Source currency code (e.g., USD, EUR)",
                            "default": "USD",
                        },
                        "to_currency": {
                            "type": "string",
                            "description": "Target currency code (e.g., KRW, JPY, EUR)",
                            "default": "KRW",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "convert_to_krw",
                "description": "Convert a USD amount to Korean Won. Use when user asks about stock price in won or Korean currency.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "usd_amount": {
                            "type": "number",
                            "description": "Amount in USD to convert",
                        }
                    },
                    "required": ["usd_amount"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_stock_candles",
                "description": "Get historical stock price data (OHLCV) for charting. Period is default 30 days.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Company ticker symbol (e.g. AAPL)",
                        },
                        "resolution": {
                            "type": "string",
                            "description": "Candle resolution. D=Daily, W=Weekly, M=Monthly, 1, 5, 15, 30, 60=Minutes.",
                            "default": "D",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days of history to fetch.",
                            "default": 30,
                        },
                    },
                    "required": ["ticker"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_to_favorites",
                "description": "Add a company to the user's favorites/watchlist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Company ticker symbol to add (e.g. AAPL, MSFT). If user says '관심기업 등록해줘' or '추가해줘', extract the company name/ticker.",
                        }
                    },
                    "required": ["ticker"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "remove_from_favorites",
                "description": "Remove a company from the user's favorites/watchlist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Company ticker symbol to remove (e.g. AAPL, MSFT). If user says '관심기업 삭제해줘', '제거해줘', or '빼줘', extract the company name/ticker.",
                        }
                    },
                    "required": ["ticker"],
                },
            },
        },
    ]

