"""Documents Admas AI makes on request: PowerPoint, Word and PDF.

The planner marks the request (kind "document", with a format), the usual
tools fetch the official data, the model writes a structured outline
(outline.py), and code lays it out in the Ministry's design (slides.py,
word.py, pdf.py). The model never writes the file itself, and every chart and
table comes straight from the fetched data.
"""
