# Interview notes: EV adoption in India

Talking points for discussing this project. Every number here is reproduced by the notebook.

## The 30-second version

> "For my capstone I studied EV adoption in India by combining a 28-question consumer survey I designed and ran with government registration data, charging-infrastructure data and IEA benchmarks. When I revisited it to publish, I found and fixed several analytical errors: a filtering bug that produced a negative growth rate, a forecast distorted by a partial year, and a classifier whose headline accuracy was mostly circular. The corrected conclusions are narrower but defensible. India's EV market is a two- and three-wheeler story growing at a slowing rate. About 44% of surveyed residents intend to buy an EV next and 38% are undecided. And demographics don't predict intent in my sample; attitudes do."

## Findings I can defend

| Claim | Number | Why it holds |
|---|---|---|
| Market size and trajectory | 2,392 (2014) → 1.53M (2023); YoY +209% (2022) → +49% (2023); Jan 2024 +39% vs Jan 2023 | Registration file matches Rajya Sabha figures within 0.1% per financial year |
| Segment mix | 2W + 3W = 94% of 2023 registrations; cars 5% | Direct count |
| India behind in *cars* | ~2% EV share of new car sales vs 18% world (2023) | IEA, cars only |
| Car-stock growth | India 55.5% CAGR 2015–23 (USA 36%, world 54%), but from 4,400 cars | Fixed IEA filter |
| Infrastructure association | Spearman ρ = 0.92 across 32 states | Rank-based, robust to outliers |
| Survey intent | 44% likely [36–53%], 38% undecided (n = 125 Indian residents) | Wilson CI |
| Top concerns | Charging 56%, upfront cost 51%, battery cost 50%, statistically tied | Overlapping CIs |
| Home charging preferred | 64% vs 37% public | Wilson CI |
| Demographics don't predict intent | ROC AUC 0.51 ± 0.11 (demographic-only, 100 CV fits) | Repeated stratified CV |
| NRI = resident on intent | 48% vs 44%, Fisher p = 0.65 | |
| TCO breakeven | ~5.2 years at ₹4L gap, 12k km/yr; 3.2 yrs at 20k km/yr | Arithmetic on stated assumptions |

## Questions to expect, and honest answers

**"Your original model had 75.6% accuracy. What happened?"**
It was a single 41-row holdout against a 55.6% majority baseline, and its top predictor was "opinion of EVs = very positive", which is close to asking the outcome in different words. With repeated cross-validation the full model scores about 64–69% for Indian residents. Removing the attitude questions drops it to chance (AUC ≈ 0.5). So the survey can't tell you *who* will adopt, only how many say they will and why they hesitate. I'd rather say that than present a model that doesn't hold.

**"Why not use the random forest? It scored higher."**
The original comparison was 39% vs 75.6%, but those were different problems: a 5-class target against a binary one. On the same target, folds and features, the two are within noise of each other (0.69 vs 0.64 accuracy, ±0.08–0.09). With 125 rows, model choice is not the bottleneck; signal is.

**"What's your forecast for 2025?"**
I don't present one. A linear fit is the wrong shape. A log-linear fit backtests well but assumes 87% growth a year, which implies +106% in 2024. Growth had already slowed to +49% in 2023, and January 2024 ran +39% on January 2023. One month is a weak signal, but it points the same way. Ten annual points can't separate exponential growth from an S-curve that is levelling off. I'd want monthly data, a saturation model, and policy variables such as subsidy changes before forecasting. I removed the ARIMA because it had five parameters on ten observations and didn't converge.

**"Does charging infrastructure drive adoption?"**
The data can't say. States with more chargers have more EVs, but bigger states have more of everything, and chargers follow demand as much as they create it. One interesting pattern: states with far more EVs than their charger count predicts (UP, Bihar, Assam) are e-rickshaw markets, where vehicles charge at depots or at home.

**"Is your survey representative?"**
No, and I say so up front. It was a convenience sample collected through personal networks in about 20 hours. It skews towards Kerala, the Gulf diaspora, women and graduates. I separated out the 69 NRIs and analysed only residents living in India for the headline numbers. Results describe these respondents, not India.

**"How did you handle respondent privacy?"**
The raw responses stay private. I published a derived file with timestamps and free text removed (the location field had village and building names), coarsened categories, and local suppression to k = 3 on the quasi-identifiers. I also removed one under-18 respondent.

**"What would you do with more time?"**
- A sample of 400+ drawn by quota across states, so that ±5-point estimates and subgroup comparisons become possible.
- Measured behaviour, such as test drives or dealer visits, instead of only stated intent.
- Normalising state adoption by population or total vehicle registrations before relating it to chargers.
- A TCO model for two-wheelers, which is where most of the market is.

## What this project shows about how I work

- I audit my own work and withdraw conclusions that don't hold, rather than defending them.
- I cross-check data across sources (the registration file against Rajya Sabha totals) and test models against data they weren't fitted on (backtests).
- I report uncertainty (confidence intervals, CV spread, baselines) alongside every estimate.
- I treat respondent privacy as a design constraint, not an afterthought.
