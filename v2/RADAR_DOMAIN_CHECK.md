# Radar primary-source domains: check of 2026-10-25

Every domain in `v2/radar_primary.json` was opened directly on 2026-10-25 (curl, the built-in browser or WebFetch;
**no Tavily credits**): does it exist, does it list dated announcements, and where is the list? Fixes are applied in
`v2/radar_primary.json` and noted in `v2/RADAR_PREREG.md` before the first radar run.

| Kind / state | Domain | Exists | Dated announcements | List URL | Action |
|---|---|---|---|---|---|
| electricity / Maharashtra | mahadiscom.in | yes | yes (news list; e.g. item dated 16 Oct 2026) | mahadiscom.in/news-latest-announcements/ ; mahadiscom.in/custom/press_release.php | keep |
| electricity / Delhi | derc.gov.in | yes | yes | derc.gov.in/notices/press-release ; /commissions-proceedings-orders/general-order | keep |
| electricity / Uttar Pradesh | uperc.org | yes (home page redirects to Default2.aspx) | yes (page dated 25 Oct 2026; orders via page menu) | uperc.org/Default2.aspx → Tariff Orders | keep |
| electricity / Karnataka | kerc.karnataka.gov.in | yes | yes (e.g. "DSPV Generic tariff 25.08.2026") | kerc.karnataka.gov.in/96/tariff-order/Kn | keep |
| electricity / Tamil Nadu | tnerc.gov.in | **no response** (https and http) | — | — | **replace with tnerc.tn.gov.in** (exists; Tariff Orders list, dates up to 22/10/2026: tnerc.tn.gov.in/TariffOrders.aspx) |
| electricity / Gujarat | gercin.org | yes | yes | gercin.org/orders/tariff_orders | keep |
| electricity / Madhya Pradesh | mperc.in | yes | yes (FY 2026-27 retail tariff order) | mperc.in/page/tariff-orders-issued-by-mperc | keep |
| electricity / Jammu and Kashmir | jkserc.nic.in | **no response** | — | — | **replace with jpdcl.jk.gov.in** (exists; tariff orders incl. "Tariff Order for the FY 2026-27": jpdcl.jk.gov.in/#tariff). The regulator's own site jercjkl.nic.in did not respond from here either |
| lpg, petrol, diesel / all India | iocl.com | yes (JavaScript bot check; opens in a browser) | yes ("Last updated on" dates, e.g. 14.2 kg Indane 7 Jun 2026, 19 kg 1 Oct 2026) | iocl.com/prices-of-petroleum-products ; iocl.com/petrol-diesel-price | keep |
| milk / Gujarat and all India | amul.com | yes | **no dates on the home page; press-release page in maintenance** | — | keep (flag: weak primary source) |
| milk / Karnataka | kmfnandini.coop | yes (www.kmfnandini.coop; bare domain gives HTTP 409) | **notifications are tenders, not prices** | www.kmfnandini.coop/en/blog/notification | keep (flag) |
| milk / Tamil Nadu | aavin.tn.gov.in | yes | **price list without dates** | aavin.tn.gov.in/price-list | keep (flag) |
| rail / all India | indianrailways.gov.in | yes | yes (press releases, e.g. 23 Oct 2026) | indianrailways.gov.in/documents/press-release | keep |
| bus / Maharashtra | msrtc.maharashtra.gov.in | yes | yes (circulars, news) | msrtc.maharashtra.gov.in/GeneralPages/CircularInDetails.aspx | keep |
| bus / Karnataka | ksrtc.in | yes (KSRTC booking site; links to the government site) | few dates | — | **replace with ksrtc.karnataka.gov.in** (KSRTC's government site; exists) |
| mobile / all India | trai.gov.in | yes | yes (press releases) | trai.gov.in/notifications/press-release | keep |

Summary: 16 domains checked; 13 exist as listed, 3 replaced (Tamil Nadu and J&K electricity, Karnataka bus). The three
milk domains exist but publish no dated price announcements, so milk corroboration will mostly rely on two
independent publishers (rule 3), not a primary source. Any `.gov.in` / `.nic.in` domain still counts as primary.
