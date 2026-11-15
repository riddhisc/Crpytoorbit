# Sample data

These files are the demo Aarav would upload. Dates are June–July 2024. Prices in `prices_fallback.json` are a flat daily INR series so the desk works with no network.

| File | What it contains | What you should see |
| --- | --- | --- |
| `binance_trades.csv` | Title row, trades, and two ETH withdrawals. The 1 ETH withdrawal uses hash `0xaaa…`. A blank line trails the file. | Matched to the wallet deposit. The 0.5 ETH withdrawal is `UNMATCHED_WITHDRAWAL`. |
| `wallet_transfers.json` | ETH in `0.9985` with the same hash, and 1000 USDT in with no exchange withdrawal. | Match note “matched, network fee 0.0015”. `UNMATCHED_DEPOSIT` for the USDT. |
| `wazirx_trades.csv` | An exact duplicate BTC buy, a SOL sell of 2 after only 1.2 was bought, a BTC buy 12% above the fallback price, a blank fee, a `DD/MM/YYYY` date, a comma-decimal USDT price (`83,50`), and one unparseable date. | `DUPLICATE_TRADE`, `NEGATIVE_BALANCE`, `PRICE_DEVIATION`, `MISSING_FEE`, plus an import issue (not an exception) for the bad date. The blank fee is also an import warning. |
| `unknown_exchange.csv` | Headers `Trade Time, Coin, Direction, Units, Rate, Charge`. | No built-in connector. The import API returns 422 and the Map columns screen takes over. |
| `prices_fallback.json` | Daily INR prices for BTC, ETH, SOL, and USDT from 2024-06-01 through 2024-07-31. | Used when CoinGecko is disabled or unavailable. |

Public sample addresses only. There are no private keys in this folder.
