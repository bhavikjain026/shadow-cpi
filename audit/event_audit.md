# Event audit: results/events_for_audit.csv (12 rows)

Audited 21 Oct 2026 using web search only. Nothing was run and no existing file was changed.

**5 of 12 fully correct, 3 partly, 3 wrong, 1 unclear; 9 confirmed by an independent second source.**

> **Important limit.** The audit machine's network blocked **every** original article page: bhaskar.com, indianexpress.com,
> newindianexpress.com, deccanherald.com, timesofindia, thehindu.com, ibtimes.co.in, india.com and jansatta.com.
> So step (a), "is the quote really on the page", could not be checked directly for any row. Facts were checked
> through search results and other outlets' copies of the same story. `quote_found` is therefore "unclear" for 11 rows. For one row
> (2026-07-E1) a copy of the same article shows the quoted sentence. Someone with normal internet access should open the 12
> URLs and tick the quote check. That takes about 10 minutes.

What the verdicts mean:
- **correct**: real retail event, right size, date and place.
- **partly**: real retail event, but with a smaller error (date, amount, or how widely it is applied).
- **wrong**: as recorded, it should not move the CPI (wrong product tier, not retail, or far too wide a place).
- **unclear**: sources conflict on whether it actually happened.

## Table

| id | quote found | % right | date right | retail / in scope | place & month right | 2nd source | verdict |
|---|---|---|---|---|---|---|---|
| 2026-02-E1 rail | unclear | no (5% / +5.26%, row +5.96%) | yes | one heritage line only | **no** (TN toy train applied all-India) | [Curly Tales](https://curlytales.com/travel/the-historic-nilgiri-mountain-railway-fare-increased-from-february-fare-starts-from/) (copy of the Indian Express story, not independent) | **wrong** |
| 2026-04-E1 milk MP | unclear | yes (60→63) | yes | yes (loose milk) | partly (Indore only) | [IBC24](https://www.ibc24.in/business/indore-milk-price-hike-october-2026-new-price-3777237.html) | **partly** |
| 2026-04-E2 milk MP | unclear | yes (60→64) | yes | yes (loose milk) | partly (Dhar only) | [ETV Bharat](https://www.etvbharat.com/hi/state/dhar-milk-prices-hike-by-4-rs-milk-rate-64-rupees-per-liter-madhya-pradesh-news-mps26033002737) | **partly** |
| 2026-04-E3 electricity MP | unclear | yes (4.80% avg) | yes | yes | yes | [MPERC order (official)](https://mperc.in/uploads/petition_order_document/MPERC_Pno_140_2025_State_DISCOMs_ARR_RST__ORDER_FY_2026_27_FINAL_ORDER.pdf) | correct |
| 2026-04-E4 fuel | unclear | yes for premium diesel | yes | **no** (premium Xtra Green only) | **no** (applied all-India) | [India.com](https://www.india.com/business/premium-petrol-price-xp100-petrol-rate-in-delhi-aviation-turbine-fuel-jet-fuel-lpg-cylinder-noida-gurugram-faridabad-ghaziabad-kolkata-mumbai-8363951/) | **wrong** |
| 2026-05-E1 milk national | unclear | yes (Rs 2) | yes | yes | yes | [Business Today](https://www.businesstoday.in/personal-finance/news/story/amul-mother-dairy-raise-milk-prices-by-rs-2-per-litre-from-may-14-check-new-rates-here-531378-2026-05-14) | correct |
| 2026-05-E2 fuel | unclear | yes (avg of petrol and diesel) | yes | yes | yes | [NewKerala](https://www.newkerala.com/news/a/petrol-rs-9777-delhi-after-fuel-hike-check-543.htm) | correct |
| 2026-06-E1 electricity UP | unclear | yes as announced | yes as announced | yes | yes | [Business Today](https://www.businesstoday.in/india/story/uttar-pradesh-electricity-bills-to-rise-10-in-june-as-uppcl-imposes-fuel-surcharge-534090-2026-05-30) | **unclear** |
| 2026-07-E1 milk TN | yes (via a copy) | unclear (Rs 3 vs Rs 4) | **no** (9 Jul, not 23 Jul) | yes | yes | [DT Next](https://www.dtnext.in/news/tamilnadu/private-brands-hike-milk-curd-prices-2nd-in-7-months) | **partly** |
| 2026-08-E1 milk Maharashtra | unclear | yes (Rs 2) | yes | yes | yes | [India.com](https://www.india.com/news/india/maharashtra-milk-price-hike-cow-buffalo-milk-prices-to-rise-by-rs-2-per-litre-from-august-11-check-updates-on-diary-products-8496805/) | correct |
| 2026-09-E1 milk MH+Delhi | unclear | **no** (+9.7% wholesale, row +14.57%) | yes | **no** (wholesale buffalo milk) | **no** (Mumbai only, not Delhi) | [Business Today](https://www.businesstoday.in/amp/india/story/mumbai-milk-prices-to-rise-by-rs-9-from-september-1-check-new-rates-551994-2026-08-28) | **wrong** |
| 2026-09-E2 electricity J&K | unclear | yes (6.83% avg) | yes | yes | yes | [Kashmir Reader](https://kashmirreader.com/2026/08/22/jk-power-tariff-hiked-by-6-83-from-september-01/) | correct |

"Confirmed by an independent second source" (9) counts rows whose amount, date and place are backed by a separate outlet:
04-E1, 04-E2, 04-E3, 04-E4, 05-E1, 05-E2, 06-E1 (the announcement only), 08-E1 and 09-E2. It leaves out 02-E1 (the only copy repeats the
same story), 07-E1 (other outlets give a different amount and date) and 09-E1 (other outlets contradict the row).
Only **04-E3** has an official second source (the MPERC tariff order). No IOCL, PPAC, dairy or JERC notice could be opened.

Note on how % is made: for milk rows with only a rupee amount, the code divides the amount by the **all-India DoCA average
milk price** (about Rs 60–62). That works when the local price is near Rs 60. It breaks badly for Mumbai buffalo milk (about Rs 100). See 09-E1.

## Notes on events that are not fully correct

**2026-02-E1 (rail, wrong).** The rise is real: Southern Railway raised **base** fares on the Nilgiri Mountain Railway by 5% from Sat
21 Feb 2026. Example: Mettupalayam–Coonoor second class went from Rs 190 to Rs 200. But it is one heritage toy-train line in Tamil Nadu,
and the row is applied as an **all-India** rail change (scope "national", applied +1.7% after the day share). Also, +5.96% matches
neither the 5% headline nor 190→200 (+5.26%). It may come from another fare pair on the page.

**2026-04-E1 and 2026-04-E2 (MP milk, both partly). Same rise counted twice?** Not literally. They are different cities and
different sellers:
- E1: Indore doorstep/loose milk, Rs 60 → 63.
- E2: Dhar district milk producers' union, Rs 60 → 64.

Both took effect 1 Apr 2026. But they are two local pieces of **one statewide wave**: Dairynews7x7 reports Rs 2–4 rises across Indore,
Ujjain, Dhar, Dewas, Bhopal and Jabalpur on 1 Apr. Each row gets the **full Madhya Pradesh milk weight**, so MP milk moves by about
+11.6% in total instead of about +5–6%. The E1 article's address also includes "dhar-indore", so it may already report the Dhar rise.
In effect this is double counting.

**2026-04-E4 (premium fuel, wrong).** IOCL raised only **XP100 petrol (Rs 149→160)** and **Xtra Green premium diesel
(Rs 91.49→92.99)**, plus commercial LPG and jet fuel. The source's own headline says there was no change for domestic LPG or regular
petrol and diesel. The CPI fuel items are ordinary petrol and diesel, so this +1.64% "national fuel" row should not be there. The code's
non-consumer filter caught commercial LPG but not "premium" fuels.

**2026-06-E1 (UP electricity, unclear).** UPPCL did announce a 10% FPPAS surcharge on June 2026 bills (circular of 29 May; the
calculated 20.61% was capped at 10%). But several later reports say **UPERC halted it** before collection, pending a final decision:
[Free Press Journal](https://www.freepressjournal.in/business/up-electricity-bill-hike-put-on-hold-millions-of-consumers-get-relief-as-10-fuel-surcharge-stopped),
[Nayan Jagriti](https://nayanjagriti.com/up-electricity-relief-news-10-percent-surcharge-stay-uppcl/28959/),
[India Headlines](https://indiaheadlinestv.com/uttar-pradesh/electricity-bills-increase-up-10-fuel-surcharge-put-hold/).
None of these is an official order, and the final outcome was not found. If the hold stuck, UP households never paid it.

**2026-07-E1 (Arokya milk, partly).** Arokya (Hatsun) did raise milk and curd prices in July. A copy of the cited 9 Jul New Indian
Express item ([dairynews.today](https://dairynews.today/news/aavin_reduces_sugar_in_lassi_as_arokya_increases_milk_prices_4260590.html))
says "Rs 3 per litre". DT Next, NewKerala and SocialNews say **Rs 4 per litre from Thu 9 Jul 2026**. The row's effective date
of 23 Jul does not match. It seems to come from the page date (source_date 22 Jul), not the article. Using 23 Jul cuts the July day share
from 23/31 to 9/31. Other TN brands (Amirthaa, Veda, Sun and others) followed on 21 Jul, and a further round came later.

**2026-09-E1 (+14.57% milk, Maharashtra and Delhi, wrong).** Not a retail rise of that size, and not in Delhi. What happened:
- The **Mumbai Milk Producers Association** raised the **wholesale rate for fresh (tabela) buffalo milk from Rs 93 to Rs 102 per litre**
  (+9.7%), from 1 Sep 2026 to 28 Feb 2027.
- Expected retail for that loose buffalo milk in Mumbai is about Rs 100 → 110 (about +10%; up to Rs 112 in South Mumbai).
- Branded packet milk (Amul, Gokul and others) is priced separately and was not part of it.
- "New Delhi" is only the article's dateline.
- The 14.57% is Rs 9 divided by the all-India average milk price (Rs 61.77). The right base is about Rs 93–100.

This row alone applies +1.48% to milk in Maharashtra and Delhi.

## Possibly missed events (seen while searching; not audited, not part of the 12)

- Petrol and diesel raised again on **19 May 2026** (Delhi petrol Rs 97.77 → 98.64, diesel Rs 90.67 → 91.58): [DNP India](https://www.dnpindia.in/states/second-fuel-price-hike-within-a-week-pushes-delhi-petrol-rate-from-rs-97-77-to-rs-98-64-heres-what-gets-dearer-check/603127/)
- Sanchi (MP cooperative) milk +Rs 2/litre from **15 May 2026**: [Amar Ujala](https://www.amarujala.com/madhya-pradesh/bhopal/milk-prices-rise-again-in-madhya-pradesh-sanchi-hikes-rates-by-2-per-liter-effective-tomorrow-congress-corn-2026-05-14)
- Gokul cow milk +Rs 2 from **21 May 2026** (Mumbai and nearby areas): [Pune Mirror on X](https://x.com/ThePuneMirror/status/2055945279611023812)
- **October 2026 (sealed month):** Indore doorstep milk +Rs 2 from 1 Oct 2026 ([IBC24](https://www.ibc24.in/business/indore-milk-price-hike-october-2026-new-price-3777237.html));
  [Free Press Journal](https://www.freepressjournal.in/indore/indore-milk-price-hike-milk-to-cost-68-per-litre-from-october-1-home-delivery-charges-extra) gives a different figure (Rs 68).
