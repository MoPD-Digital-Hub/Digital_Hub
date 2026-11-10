"""Admas AI: a data assistant over typed tools.

    question -> plan (one model call, JSON) -> resolve entities (catalog, no model)
             -> fetch data (typed tools, no model) -> compose (model, streamed)
             -> render tables/charts (code) -> verify numbers (code)

See docs/ai.md. ai.consumers and ai.api serve the app and web chat from
this pipeline through ai.engine.compat.
"""
