"""Amharic answers: the characters they may use, and the standard terms they should use.

The Ministry model sometimes writes a word it does not know in Amharic in
another script ("ያልمركزነት", "በгосударство"). Two defences:

- ALLOWED_PATTERN: the gateway's vLLM is asked to generate only these
  characters (structured outputs, a regular expression), so Arabic, Cyrillic,
  Chinese and other letters cannot be produced at all. Ethiopic, Latin (for
  names, abbreviations and English terms), digits, punctuation and HTML remain.
- GLOSSARY: standard Amharic for the government and economic terms the
  answers use, given to the writer.

The glossary is a draft: it must be reviewed by someone who writes the
Ministry's official Amharic, and corrected or extended here.
"""

ALLOWED_PATTERN = (
    r"[\t\n\r -~ -ɏሀ-᎟ⶀ-⷟꬀-꬯"
    r"‐-‧‰-⁞₠-⃏℀-⅏]*"
)

# (English, Amharic). Reviewed: no (draft, 2026-11-12).
GLOSSARY = (
    ("Ministry of National Strategy (MoNS)", "የብሔራዊ ስትራቴጂ ሚኒስቴር"),
    ("Ministry of Planning and Development", "የፕላንና ልማት ሚኒስቴር"),
    ("ministry", "ሚኒስቴር"),
    ("minister", "ሚኒስትር"),
    ("state minister", "ሚኒስትር ዴኤታ"),
    ("public bodies / institutions", "የመንግሥት ተቋማት"),
    ("federal government", "የፌዴራል መንግሥት"),
    ("regional state", "ክልል"),
    ("policy area", "የፖሊሲ መስክ"),
    ("strategic goal", "ስትራቴጂያዊ ግብ"),
    ("key performance indicator (KPI)", "ቁልፍ የአፈጻጸም አመልካች"),
    ("performance score", "የአፈጻጸም ውጤት"),
    ("indicator", "አመልካች"),
    ("target", "ዒላማ"),
    ("Ten-Year Development Plan", "የአሥር ዓመት የልማት ዕቅድ"),
    ("Homegrown Economic Reform", "ሀገር በቀል የኢኮኖሚ ማሻሻያ"),
    ("gross domestic product (GDP)", "አጠቃላይ የሀገር ውስጥ ምርት"),
    ("economic growth", "የኢኮኖሚ ዕድገት"),
    ("inflation", "የዋጋ ግሽበት"),
    ("exports", "የወጪ ንግድ"),
    ("imports", "የገቢ ንግድ"),
    ("foreign direct investment", "የውጭ ቀጥተኛ ኢንቨስትመንት"),
    ("remittances", "ከውጭ የሚላክ ገንዘብ (ሐዋላ)"),
    ("exchange rate", "የውጭ ምንዛሪ ተመን"),
    ("foreign currency reserves", "የውጭ ምንዛሪ ክምችት"),
    ("budget", "በጀት"),
    ("government revenue", "የመንግሥት ገቢ"),
    ("tax", "ግብር"),
    ("public debt", "የመንግሥት ዕዳ"),
    ("fiscal year", "የበጀት ዓመት"),
    ("fiscal decentralization", "የፊስካል ያልተማከለ አስተዳደር"),
    ("public investment", "የመንግሥት ኢንቨስትመንት"),
    ("quarter (of a year)", "ሩብ ዓመት"),
    ("percent", "በመቶ"),
    ("million / billion", "ሚሊዮን / ቢሊዮን"),
    ("Sustainable Development Goals (SDGs)", "ዘላቂ የልማት ግቦች"),
    ("poverty", "ድህነት"),
    ("unemployment", "ሥራ አጥነት"),
    ("food security", "የምግብ ዋስትና"),
    ("stunting", "መቀንጨር"),
    ("maternal mortality", "የእናቶች ሞት"),
    ("school enrolment", "የትምህርት ተሳትፎ"),
    ("literacy", "ማንበብና መጻፍ"),
    ("access to electricity", "የኤሌክትሪክ አገልግሎት ተደራሽነት"),
    ("International Monetary Fund (IMF)", "ዓለም አቀፉ የገንዘብ ድርጅት (IMF)"),
    ("World Bank", "የዓለም ባንክ"),
    ("African Union", "የአፍሪካ ኅብረት"),
    ("United Nations", "የተባበሩት መንግሥታት ድርጅት"),
    ("National Bank of Ethiopia", "የኢትዮጵያ ብሔራዊ ባንክ"),
)

RULES = """

Writing Amharic:
- Write in standard written Amharic, in Ethiopic script.
- Use these standard terms (English = Amharic): {terms}.
- For a term not in that list whose Amharic you are unsure of, write the Amharic you know and add the English term in Latin letters in parentheses, for example "የፊስካል ፖሊሲ (fiscal policy)". Never write a word in any other script."""


def rules():
    """The writer's Amharic instructions, with the glossary."""
    return RULES.format(terms="; ".join(f"{english} = {amharic}" for english, amharic in GLOSSARY))
