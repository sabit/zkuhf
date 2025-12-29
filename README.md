# Example

```python
from zkuhf import ZkUhfReader

r = ZkUhfReader()
r.connect()

print("Press Enter to read")
input()

card = r.read_once()
print("CARD:", card)

r.close()
```
