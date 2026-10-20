import sys
import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"MT5_ERROR init: {mt5.last_error()}", file=sys.stderr)
    sys.exit(1)

account = mt5.account_info()
if account is None:
    print(f"MT5_ERROR account_info: {mt5.last_error()}", file=sys.stderr)
    mt5.shutdown()
    sys.exit(1)

positions = mt5.positions_get(symbol="XAUUSD") or ()
if positions:
    parts = []
    for p in positions:
        side = "LONG" if p.type == mt5.ORDER_TYPE_BUY else "SHORT"
        parts.append(f"{side} vol={p.volume} entry={p.price_open} pnl={p.profit:.2f}")
    pos_str = " ; ".join(parts)
else:
    pos_str = "AUCUNE position"

print(f"equity={account.equity:.2f} balance={account.balance:.2f} | {pos_str}")
mt5.shutdown()
