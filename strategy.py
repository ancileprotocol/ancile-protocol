def get_signal(stats):
    if not stats:
        return "HOLD"

    c5m  = stats["change5m"]
    c1h  = stats["change1h"]
    c6h  = stats["change6h"]
    c24h = stats["change24h"]

    print(f"  5m: {c5m:+.2f}% | 1h: {c1h:+.2f}% | 6h: {c6h:+.2f}% | 24h: {c24h:+.2f}%")

    if c5m > 0.3 and c1h > 0.5 and c6h > 1:
        return "BUY"

    if c5m < -1 and c1h < -2:
        return "SELL"

    return "HOLD"
