# Writing a connector

A connector subclasses `Connector` and implements:

- `detect(filename, text, headers) -> bool` using a header signature.
- `parse(filename, text) -> (list[CanonicalTxDraft], list[ImportIssueDraft])`.

Never raise on a bad row. Record an `ImportIssue` with one of: `unparseable date`, `non-numeric quantity`, `unknown side`, `negative quantity`, `unknown ticker`.

## CoinDCX sketch

```python
class CoindcxConnector(Connector):
    name = "coindcx"

    def detect(self, filename: str, text: str, headers: list[str]) -> bool:
        return "Trade ID" in headers and "Market" in headers and "Fee Amount" in headers

    def parse(self, filename: str, text: str):
        drafts, issues = [], []
        # Map Date, Market, Side, Price, Quantity, Fee Amount into CanonicalTxDraft.
        # Convert IST to UTC. Blank fee -> fee 0 and ImportIssue(..., "missing fee").
        return drafts, issues
```

Register it in `builtin_connectors()` and add a test that parses a tiny CSV, including one bad row, and asserts the issue reason rather than an exception.

## Test template

```python
def test_coindcx_parses_and_skips_bad_rows():
    text = "Trade ID,Market,Side,Price,Quantity,Fee Amount\\n1,BTCINR,buy,1,0.01,0.1\\nbad,BTCINR,buy,1,x,0\\n"
    drafts, issues = CoindcxConnector().parse("c.csv", text)
    assert len(drafts) == 1
    assert issues[0].reason == "non-numeric quantity"
```
