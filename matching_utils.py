def match_trades(trades, side="long"):
    matched = []
    entries = []
    for trade in trades:
        if side == "long" and trade.get("direction") == "buy":
            entries.append(trade)
        elif side == "short" and trade.get("direction") == "short":
            entries.append(trade)
        elif side == "long" and trade.get("direction") == "sell" and entries:
            entry = entries.pop(0)
            matched.append({
                "Entry Date": entry["date"],
                "Entry Price": entry["price"],
                "Exit Date": trade["date"],
                "Exit Price": trade["price"],
                "PnL": trade["price"] - entry["price"],
                "Shares": entry["shares"]
            })
        elif side == "short" and trade.get("direction") == "cover" and entries:
            entry = entries.pop(0)
            matched.append({
                "Entry Date": entry["date"],
                "Entry Price": entry["price"],
                "Exit Date": trade["date"],
                "Exit Price": trade["price"],
                "PnL": entry["price"] - trade["price"],
                "Shares": entry["shares"]
            })
    return matched
