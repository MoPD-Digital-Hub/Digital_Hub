# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users of the Admas AI web page are ministry leaders: directors and senior officials of the Ministry of National Strategy (MoNS, formerly the Ministry of Planning and Development) who check figures quickly, often right before a meeting or briefing. The same assistant also answers in the ADMAS mobile app (Flutter), which reads the same answers over `/ws/chat/` and `/api/ai-chat/`.

## Product Purpose

The Digital Hub is MoNS's internal data platform: a server-rendered dashboard (indicators, SDG pages, ministry performance) plus Admas AI, an assistant that answers questions about Ethiopia's numbers in English or Amharic. Success is a leader getting a correct figure, with its period and its source, fast enough to use it in the meeting they are walking into.

## Positioning

Admas AI answers only from three national sources, and every answer names which: the national time-series database (economy and society indicators), DPMES (performance scores and KPIs of ministries, agencies, policy areas and strategic goals), and Ethiopia's national SDG platform (sdg.mopd.gov.et). Tables and charts are built from the fetched data, never written by the model, and the written explanation is checked against that data.

## Operating Context

- The page lives inside the dashboard frame (left navigation, top bar, theme picker with light, dark and colour themes); it must stay inside that frame.
- Questions arrive typed or by voice (browser speech recognition, English). Answers stream in; chats are kept, auto-titled from the first question, renamable and deletable.
- Years: time-series and DPMES use the Ethiopian calendar (EC); the SDG platform uses Gregorian years.
- Content is bilingual: English and Amharic (Ethiopic script) in questions, answers, chat titles and data labels.

## Capabilities and Constraints

- Answer HTML is shared with the mobile app: `<h4>`, `<table>`, `<chart-data>` JSON blocks and `<p class="ai-source">` lines. Web-only presentation is added client-side; the server output may only gain fields, never lose or rename them.
- Data blocks: time series by year/quarter/month, ministry and policy-area scores with DPMES colour bands, KPI lists, rankings, SDG indicators (national or by region, sex, age, area, education, wealth) and SDG goal overviews.
- No translation or read-aloud (removed); Copy is available.
- Stack: Django templates, plain JavaScript, ApexCharts, Tabler icons, Bootstrap-based dashboard theme.

## Brand Commitments

- Names: "Admas AI", "MoNS - Ministry of National Strategy", "Digital Hub".
- Admas AI page (2026-11-11, supersedes the earlier rejection of chat layouts): the user asked for a design like Claude's chat (claude.ai): the question box at the bottom, chats in a left list, a greeting on an empty chat, the answer as readable text without a bubble. Keep it free of decoration (gradients, glows, badges, ornamental icons).

## Evidence on Hand

- Real answers with real figures from the three sources (local chats in development).
- Logo mark: `core/static/assets/images/token-branded_ais.png`.
- No testimonials, usage numbers or endorsements exist; none may be invented.

## Product Principles

- The figure first: the direct answer, its period and its source come before explanation.
- Every number shows where it came from.
- Bilingual by default: Amharic is a first-class script, not a fallback.
- Fast to scan for a leader in a hurry; nothing on the page competes with the numbers.

## Accessibility & Inclusion

Readable in light and dark themes, keyboard operable, reduced motion respected, Ethiopic script rendered properly.
