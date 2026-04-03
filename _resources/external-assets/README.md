# External Assets

This directory contains ZarishSphere's first-pass migration audit for external healthcare repositories stored under `/home/ariful/Desktop/zarishsphere/_cloned`.

Generated artifacts:

- `migration-manifest.json`: machine-readable source inventory and target repo mapping.
- `MIGRATION_AUDIT.md`: human-readable summary and recommended migration order.

To refresh the inventory:

```bash
python3 tools/external_inventory.py
```
