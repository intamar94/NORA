# NORA pipeline

The production flow is intentionally separated into stages:

1. Quality Gate validates the current NORA data interface.
2. Discovery runs only after the Quality Gate succeeds.
3. Earth Engine smoke tests remain independent and do not trigger historical ingestion.

Current pilot region: Alto Xingu. The data interface is generic so additional regions can be added without renaming the core pipeline.
