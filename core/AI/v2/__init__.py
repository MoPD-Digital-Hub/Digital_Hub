"""Admas AI v2: a data assistant over typed tools.

    question -> plan (one model call, JSON) -> resolve entities (catalog, no model)
             -> fetch data (typed tools, no model) -> compose (model, streamed)
             -> render tables/charts (code) -> verify numbers (code)

See docs/ai-v2.md. v1 (AI.consumers, AI.application) is untouched and keeps
serving /ws/chat/ until clients move to /ws/v2/chat/.
"""
