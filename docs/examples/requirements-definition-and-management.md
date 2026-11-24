# Requirements Definition and Management: a small Python example

This example keeps three things traceable: the requirement, the implementation,
and the verification test.

| ID | Requirement | Implementation | Verification |
| --- | --- | --- | --- |
| REQ-1 | Reject a negative package weight. | `shipping_cost` validation | `test_shipping_cost_rejects_negative_weight` |
| REQ-2 | Charge `$5 + ($2 * weight_kg)` for standard delivery. | Base-rate expression | `test_shipping_cost_applies_the_defined_base_rate_and_express_fee` |
| REQ-3 | Add `$10` for express delivery. | `express` fee expression | `test_shipping_cost_applies_the_defined_base_rate_and_express_fee` |

```python
from synlynk.examples import shipping_cost

shipping_cost(weight_kg=3, express=True)  # 21.0
```

When a requirement changes, update its row, the function's requirement list,
and its test together. That small traceability loop is the management part of
the example.
