# Recall check: retail price changes in India, Jan–Sep 2026

Report only, written 21 Oct 2026 from web search. Nothing was run, no event is added by hand, and no rule changes.
The pipeline's 12 events are in `results/events_for_audit.csv` (audited in `audit/event_audit.md`, PR
bhavikjain026/shadow-cpi#4).

**FOUND** = matches one of those 12 events. **MISSED** = not among them. Some MISSED items still reach the nowcast
another way (the IOCL LPG list, PPAC petrol prices, or the government milk price spine). The last column says which.

**Excluded by the brief:** wholesale prices (e.g. Mumbai tabela buffalo milk Rs 93 → 102, 1 Sep), commercial
LPG, premium fuels (XP100 and Xtra Green, 1 Apr), fines and penalties. **Also left out:** proposals not in force by 30 Sep
(Nandini +Rs 8; Karnataka bus fares +25–40%; mobile tariff "hike expected" stories) and items whose year I could not
confirm (Verka Rs 2 "from 30 April").

**Sources:** "official" means a regulator or company document, or All India Radio / PIB. Everything else is a
news report. The audit network could not open most pages directly, so details come from search results.

## Reference list (29 changes)

### Milk (packet and loose retail)

| # | Effective | Where | Change | Best source | Status | Reaches the nowcast another way? |
|---|---|---|---|---|---|---|
| M1 | 28 Feb | Maharashtra (Chitale) | +Rs 2/litre (cow milk 58 → 60) | [Dairy Dimension](https://dairydimension.com/chitale-dairy-milk-price-hike-maharashtra/) (date tag inconsistent) | MISSED | milk spine |
| M2 | 1 Apr | Madhya Pradesh, loose milk (Indore 60 → 63, Dhar 60 → 64, other cities Rs 2–4) | +Rs 2 to 4/litre | [IBC24](https://www.ibc24.in/business/indore-milk-price-hike-october-2026-new-price-3777237.html), [ETV Bharat](https://www.etvbharat.com/hi/state/dhar-milk-prices-hike-by-4-rs-milk-rate-64-rupees-per-liter-madhya-pradesh-news-mps26033002737) | **FOUND** (04-E1, 04-E2, counted twice) | milk spine |
| M3 | 14 May | National (Amul, Mother Dairy) | +Rs 2/litre | [Business Today](https://www.businesstoday.in/personal-finance/news/story/amul-mother-dairy-raise-milk-prices-by-rs-2-per-litre-from-may-14-check-new-rates-here-531378-2026-05-14) | **FOUND** (05-E1) | milk spine |
| M4 | 15 May | Madhya Pradesh (Sanchi cooperative) | +Rs 2/litre | [Amar Ujala](https://www.amarujala.com/madhya-pradesh/bhopal/milk-prices-rise-again-in-madhya-pradesh-sanchi-hikes-rates-by-2-per-liter-effective-tomorrow-congress-corn-2026-05-14) | MISSED | milk spine |
| M5 | 21 May | Maharashtra: Mumbai, Thane, Raigad, Palghar (Gokul cow milk) | +Rs 2/litre | [Pune Mirror](https://x.com/ThePuneMirror/status/2055945279611023812), [Pune Pulse](https://www.mypunepulse.com/gokul-milk-price-hike-after-amul-gokul-raises-cow-milk-rates-check-new-prices/) | MISSED | milk spine |
| M6 | 22 May | Bihar, Jharkhand (Sudha) | +Rs 2/litre (Gold 65 → 67) | [AgriMoon](https://agrimoon.com/sudha-milk-prices-hiked-by-rs2-per-litre/) | MISSED | milk spine |
| M7 | 1 Jun | Kerala (Milma) | +Rs 4/litre | [The News Mill](https://thenewsmill.com/2026/05/milma-raises-milk-price-by-%E2%82%B94-per-litre-from-june-1-in-keralam/) | MISSED | milk spine |
| M8 | 9 Jul | Tamil Nadu (Arokya) | +Rs 4/litre (cited page says Rs 3) | [NewKerala](https://www.newkerala.com/news/a/private-dairies-tamil-nadu-raise-milk-curd-prices-681.htm) | **FOUND** (07-E1, date wrong) | milk spine |
| M9 | 21 Jul to late Jul | Tamil Nadu (Amirthaa, Veda, Sun, then Tirumala, Heritage, Dodla and others) | +Rs 2 to 4/litre (up to Rs 6 in total since July) | [DT Next](https://www.dtnext.in/news/tamilnadu/private-brands-hike-milk-curd-prices-2nd-in-7-months), [News Today](https://newstodaynet.com/2026/07/27/private-dairies-hike-milk-prices-again/) | MISSED | milk spine |
| M10 | 11 Aug | Maharashtra (cooperative and private dairies) | +Rs 2/litre | [India.com](https://www.india.com/news/india/maharashtra-milk-price-hike-cow-buffalo-milk-prices-to-rise-by-rs-2-per-litre-from-august-11-check-updates-on-diary-products-8496805/) | **FOUND** (08-E1) | milk spine |
| M11 | 21 Sep | Tamil Nadu (Arokya) | +Rs 4/litre (litre pack to Rs 86) | [LiveChennai](https://www.livechennai.com/detailnews.asp?newsid=83215) | MISSED | milk spine |
| M12 | 26 Sep | Tamil Nadu (Dodla, Heritage and other private brands) | up to +Rs 4/litre | [DT Next](https://www.dtnext.in/news/tamilnadu/private-dairies-to-hike-milk-curd-prices-from-saturday-aavin-faces-widening-price-gap-in-tamil-nadu) | MISSED | milk spine |

Not counted: a Rs 2 rise by TN private dairies "in Feb" (one half-sentence only, no date).

### Domestic LPG (14.2 kg)

| # | Effective | Where | Change | Best source | Status | Reaches the nowcast another way? |
|---|---|---|---|---|---|---|
| L1 | 7 Mar | National | +Rs 60 (Delhi 853 → 913, +7.0%) | [All India Radio](https://www.newsonair.gov.in/domestic-lpg-price-hiked-by-rs-60-commercial-cylinder-up-rs-115) (official) | MISSED | **yes:** IOCL list (LPG events are switched off by Amendment 1 (a)) |
| L2 | 7 Jun | National | +Rs 29 (Delhi 913 → 942, +3.2%) | [India.com](https://www.india.com/business/domestic-lpg-cylinder-price-hiked-by-rs-29-new-rates-effective-from-today-14-2-kg-lpg-cylinder-in-delhi-cost-rs-942-8438822/), [Open](https://openthemagazine.com/india/domestic-lpg-price-hiked-by-rs-29-delhi-rate-climbs-to-rs-942-per-cylinder) | MISSED | **yes:** IOCL list |

### Regular petrol and diesel (Delhi)

| # | Effective | Change | Best source | Status | Reaches the nowcast another way? |
|---|---|---|---|---|---|
| F1 | 15 May | +Rs 3 (petrol 94.77 → 97.77; diesel 87.67 → 90.67) | [All India Radio](https://newsonair.gov.in/petrol-diesel-prices-hiked-by-rs-3-per-litre-amid-spike-in-global-energy-prices/) (official) | **FOUND** (05-E2) | also PPAC from 15 May |
| F2 | 19 May | petrol +0.87 (→ 98.64), diesel +0.91 (→ 91.58) | [WebIndia123, 19 May](https://news.webindia123.com/news/Articles/India/20260519/4451914.html), [DNP India](https://www.dnpindia.in/states/second-fuel-price-hike-within-a-week-pushes-delhi-petrol-rate-from-rs-97-77-to-rs-98-64-heres-what-gets-dearer-check/603127/) | MISSED | **yes:** PPAC Delhi prices |
| F3 | 23 May | petrol +0.87 (→ 99.51), diesel +0.91 (→ 92.49) | [The Week, 23 May](https://www.theweek.in/news/biz-tech/2026/05/23/third-hike-in-10-days-petrol-diesel-prices-increased-again-by-87-91-paise-per-litre.html) | MISSED | **yes:** PPAC |
| F4 | 25 May | petrol +2.61 (→ 102.12), diesel +2.71 (→ 95.20) | [Univest](https://univest.in/blogs/petrol-price-hike-crosses-100-delhi-fourth-hike-10-days-may-2026) (weak source); Delhi still 102.12 on 21 Oct per [Goodreturns](https://www.goodreturns.in/petrol-price-in-new-delhi.html) | MISSED | **yes:** PPAC |

No change found June to September (prices flat at 102.12 / 95.20).

### Household electricity (state regulator orders and surcharges)

| # | Effective | State | Change | Best source | Status | Reaches the nowcast another way? |
|---|---|---|---|---|---|---|
| E1 | 1 Apr | Madhya Pradesh | +4.80% average | [MPERC order](https://mperc.in/uploads/petition_order_document/MPERC_Pno_140_2025_State_DISCOMs_ARR_RST__ORDER_FY_2026_27_FINAL_ORDER.pdf) (official) | **FOUND** (04-E3) | – |
| E2 | 1 Apr | Maharashtra (MSEDCL) | **cut**; no category goes up (exact % unclear) | [Social News XYZ](https://www.socialnews.xyz/2026/03/27/maha-mahavitaran-tariff-cut-to-benefit-consumers-from-april-1/) | MISSED | no |
| E3 | 1 Apr | Punjab | **cut**, domestic up to −Rs 1.50/unit, lower fixed charges | [Mercom](https://mercomindia.com/punjab-cuts-power-tariffs-for-fy-2027-as-%E2%82%B978-5-billion-surplus-emerges), [The Federal](https://thefederal.com/category/states/north/punjab/punjab-slashes-electricity-prices-2027-assembly-elections-233072) | MISSED | no |
| E4 | FY 2026-27 (order about 27 Mar) | Jharkhand | rise, all categories (% unclear) | [Mercom](https://www.mercomindia.com/jharkhand-hikes-electricity-tariffs-across-categories-for-fy-2027) | MISSED | no |
| E5 | June bills | Uttar Pradesh | +10% FPPAS surcharge as announced; later reportedly **put on hold** | [Business Today](https://www.businesstoday.in/india/story/uttar-pradesh-electricity-bills-to-rise-10-in-june-as-uppcl-imposes-fuel-surcharge-534090-2026-05-30) | **FOUND** (06-E1, status unclear) | – |
| E6 | June onwards (first monthly surcharge) | Delhi | monthly FPPAS on bills; the May 2026 surcharge is 12–18% by discom; low-use homes stay subsidised | [Business Today, 13 Jul](https://www.businesstoday.in/amp/india/story/electricity-bills-to-get-costlier-in-delhi-derc-allows-additional-fuel-and-power-surcharge-542598-2026-07-13) | MISSED | no |
| E7 | 1 Jul | Chhattisgarh | +6.23% average; domestic +30 to 50 paise/unit | [CSPDCL tariff order](https://cspdcl.co.in/CSEB/Files/tariff_order_fy2627.pdf) (official), [ETV Bharat](https://www.etvbharat.com/en/state/chhattisgarh-raises-electricity-tariffs-cong-attacks-sai-government-enn26061601315) | MISSED | no |
| E8 | 1 Sep | Jammu and Kashmir | +6.83% average | [Kashmir Reader](https://kashmirreader.com/2026/08/22/jk-power-tariff-hiked-by-6-83-from-september-01/) | **FOUND** (09-E2) | – |

Checked, no change (correctly nothing to find):
- Andhra Pradesh ([South First](https://thesouthfirst.com/andhrapradesh/no-power-tariff-hike-in-andhra-pradesh-for-fy-2026-27-government-to-bridge-rs-15790-crore-gap/))
- Assam ([SolarQuarter](https://solarquarter.com/2026/03/10/assam-electricity-regulatory-commission-keeps-power-tariffs-unchanged-for-fy-2026-27-offers-relief-to-consumers/))
- Haryana ([CSIS](https://indianstates.csis.org/articles/2026-04-01-haryana-publishes-its-tariff-order-for-2026-27/haryana-publishes-its-tariff-order-for-2026-27/))
- Uttar Pradesh base tariff ([Mercom](https://mercomindia.com/uttar-pradesh-retains-retail-power-tariffs-for-fy-2026-27))
- Tamil Nadu: no July 2026 revision found.

Not checked or not found: Gujarat, Telangana, West Bengal, Bihar, Rajasthan, Kerala, Karnataka (a possible
40–50 paise surcharge is being reported only now, in October).

### Rail and bus fares

| # | Effective | Where | Change | Best source | Status | Reaches the nowcast another way? |
|---|---|---|---|---|---|---|
| T1 | 21 Feb | Tamil Nadu, Nilgiri Mountain Railway only | +5% base fare | [Curly Tales](https://curlytales.com/travel/the-historic-nilgiri-mountain-railway-fare-increased-from-february-fare-starts-from/) | **FOUND** (02-E1, wrongly applied all-India) | – |
| T2 | 15 Apr to 31 Jul (temporary) | Maharashtra (MSRTC buses) | +10% | [Punekar News](https://www.punekarnews.in/pune-msrtc-announces-10-fare-hike-for-summer-rush-season/), [Free Press Journal](https://www.freepressjournal.in/mumbai/msrtc-extends-10-temporary-fare-hike-till-july-31-as-diesel-prices-operational-costs-continue-to-rise) | MISSED | no: **bus is not searched at all** |
| T3 | about 2 Jun (perhaps also mid-May) | Odisha (all buses) | ordinary 90 → 92 paise/km (+2.2%), AC deluxe 159 → 163 | [OmmCom News](https://ommcomnews.com/odisha-news/state-transport-authority-hikes-bus-fares-due-to-rising-diesel-prices/), [Pragativadi](https://pragativadi.com/odisha-hikes-bus-fares-as-diesel-costs-surge/) | MISSED | no: bus not searched |

Indian Railways national fares: no change in Jan–Sep 2026. The last revision was 26 Dec 2025
([All India Radio](https://www.newsonair.gov.in/indian-railways-revises-passenger-fare-structure-changes-effective-today/)).

### Mobile tariffs and GST

- **Mobile:** no confirmed Jio, Airtel or Vi tariff rise took effect in Jan–Sep 2026. Only "expected 10–20%" stories,
  e.g. [Cashify](https://www.cashify.in/news/jio-airtel-vi-tariff-hike-2026-prepaid-plans-to-cost-15-percent-more-soon). Nothing to find.
- **GST:** no rate change in 2026. The 57th GST Council meeting (8 Oct 2026) made no rate changes
  ([inkl](https://www.inkl.com/news/gst-council-meeting-2026-tax-officers-arrest-powers-scrapped-prosecution-threshold-raised-to-rs-5-crore-no-rate-changes)).
  The last rate change was 22 Sep 2025. Nothing to find.

## Result

| Kind | Reference changes | FOUND |
|---|---|---|
| Milk | 12 | 4 |
| Domestic LPG | 2 | 0 (both reach the nowcast via the IOCL list) |
| Petrol / diesel | 4 | 1 (the other 3 reach it via PPAC) |
| Electricity | 8 | 3 |
| Rail / bus | 3 | 1 |
| Mobile, GST | 0 | – |
| **Total** | **29** | **9** |

Two of the pipeline's 12 rows are not in the reference list because they are out of scope (04-E4 premium fuel,
09-E1 wholesale milk). Two rows (04-E1, 04-E2) match a single reference change.

If changes that reach the nowcast through an official observed series also count, coverage is 9 + 5 = **14 of 29**.
The milk misses matter least for the number itself: model (c) takes milk from the government price spine and never
applies milk events (`docs/preregistration.md`). Electricity and bus have no observed series, so a missed event there
is simply missing.

**Pipeline found 9 of 29 known retail price changes (recall 31%).**

The 3 most important misses:
1. **Electricity cuts on 1 Apr in Maharashtra and Punjab.** These go the opposite way to everything the pipeline found.
   Maharashtra carries a large share of the electricity weight, and electricity has no observed series, so these
   cuts are invisible.
2. **Chhattisgarh +6.23% from 1 Jul**, backed by an official tariff order. Also Delhi's monthly fuel surcharge from
   June (12–18% for May power, mainly for higher-use homes).
3. **Bus fares: MSRTC +10% (15 Apr to 31 Jul) and Odisha (June).** The event layer searches rail but not bus, so no
   bus fare change can ever be found.
