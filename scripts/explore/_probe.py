import sys, traceback, akshare as ak
def p(title, fn):
    try:
        df = fn()
        print(f"OK  | {title} | shape={df.shape}")
        print("    cols:", list(df.columns)[:20])
        print(df.head(3).to_string()[:600])
        print(df.tail(2).to_string()[:400])
    except Exception as e:
        print(f"ERR | {title} | {type(e).__name__}: {str(e)[:180]}")
    print("-"*70)
