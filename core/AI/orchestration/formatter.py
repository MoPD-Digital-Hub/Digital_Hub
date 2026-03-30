from AI.gemini.language import detect_language


def dashboard_success_message(title: str, share_url: str, language: str | None = None) -> str:
    resolved_language = language or detect_language(title or share_url)
    safe_title = str(title or "").strip()
    safe_url = str(share_url or "").strip()
    link = f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>'
    if resolved_language == "Amharic":
        if safe_title:
            return f"<p>“{safe_title}” የተባለው ዳሽቦርድዎ ተዘጋጅቷል: {link}</p>"
        return f"<p>ዳሽቦርድዎ ተዘጋጅቷል: {link}</p>"
    if safe_title:
        return f"<p>Your dashboard “{safe_title}” is ready: {link}</p>"
    return f"<p>Your dashboard is ready: {link}</p>"


def dashboard_failure_message(language: str | None = None) -> str:
    if language == "Amharic":
        return "<p>ዳሽቦርድ መፍጠር አልተሳካም። እባክዎ በኋላ ይሞክሩ።</p>"
    return "<p>Dashboard creation failed. Please try again later.</p>"


def time_series_failure_message(language: str | None = None) -> str:
    if language == "Amharic":
        return "<p>ለዚህ ጥያቄ የጊዜ-ተከታታይ መረጃ አልተገኘም።</p>"
    return "<p>No time-series data was found for this request.</p>"
