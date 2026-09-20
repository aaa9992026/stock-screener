# Data Providers

## US Market

### Company List
Source:
Nasdaq Trader Symbol Directory

Purpose:
- US stock/company universe
- Symbol search
- Newly listed stock updates

Type:
Public downloadable data files

## NSE India

### Company List
Source:
NSE Equity Securities List

Purpose:
- NSE company universe
- Symbol search
- Newly listed company updates

Type:
Official public downloadable exchange data

## OHLCV Market Data

Provider:
Yahoo Finance through yfinance

Purpose:
- Historical OHLCV
- Latest available prices
- US, NSE and supported BSE symbols

Notes:
- NSE symbols use `.NS`
- BSE symbols use `.BO`
- If a provider returns incomplete data, the screener shows a warning instead of silently using it.

## US Fundamental Data

Provider:
Yahoo Finance through yfinance

Data currently used:
- Market cap
- EPS
- Revenue
- Net income
- Profit margin
- ROE
- ROA
- Insider ownership
- Institutional ownership
- Shares outstanding
- Float shares

## Database Storage

Historical OHLCV is stored in PostgreSQL.

Each record is identified by:
- symbol
- exchange
- date

Refreshing data updates an existing date or inserts a new date. Existing historical records are not deleted during a normal refresh.