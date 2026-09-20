# Replacing a Data Provider

The screener uses a provider-based architecture so another developer can replace a market-data source without rebuilding the entire application.

## Provider Interface

Market-data providers are located under:

backend/app/services/providers/

The base provider interface is:

backend/app/services/base_provider.py

A replacement provider should implement the required methods, such as:

- get_companies()
- get_ohlcv()
- get_fundamentals() where required

## Replacing OHLCV Provider

1. Create a new provider file in:

   backend/app/services/providers/

2. Implement the same output format:

   date
   open
   high
   low
   close
   volume

3. Update the API/service layer to instantiate the new provider.

4. Add required API credentials to `.env`.

5. Test refresh using:

   POST /market/refresh/{symbol}

## API Keys

API keys should be stored in `.env`.

Do not hard-code API keys in source code.

Example:

MARKET_API_KEY=your_key_here

## Failure Handling

If a provider:
- stops responding
- changes its endpoint
- changes authentication
- returns incomplete data

the application should return an error/stale-data warning instead of silently treating old or incomplete data as current.

## Database Independence

Changing the provider does not require replacing the PostgreSQL database.

The new provider only needs to return data in the expected internal format, and the existing sync services can continue storing and updating records.

## Future Paid API

A future paid Indian or US market API can be integrated by creating a new provider adapter and replacing the provider used by the API routes.