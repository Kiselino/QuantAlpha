# Understanding Data in BRAIN: Key Concepts and Tips

> 官方教程页（BRAIN /learn）：`data` | 类别：Data | 时长：PT4M
> 来源：仓库调研素材 tutorial_pages.json（登录态抓取）| 用途：bootcamp 模块 M3 | 最后更新：2026-08-26

## Data Fundamentals
### Data Field
A named collection of data, which has constant type and business meaning. For example, 'open price' is of constant type (numeric), and it consistently means the price of a security at the starting time of the trading period. 'Close price' has the same type as 'open price', but it’s a different field as it differs in business meaning.
A Dataset is a collection of Data Fields. Dataset can be identified by its name (text format, longer and explanatory) or its dataset ID (short alphanumeric format, only relevant for advanced scripting).

#### Matrix
Basic type of field which has just one value of every date and instrument. There is no special syntax for using this in simulation. Some examples of matrix fields are close, returns, cap.

#### Vector
Type of field which has more than one value for every date and instrument. Vector data fields have to be converted into matrix data fields using vector operators before using with other operators and matrix data fields. Otherwise, an error message will be returned.
You can learn more about it here: Vector data fields


[IMAGE 内容省略——图片/多媒体]

### Dataset
A source of information on one or more variables of interest for the WorldQuant investment process. A collection of data fields. For example: “price volume data for US equities” or “analyst target price predictions for US equities". See Datasets.

## Tips on working with new data
WorldQuant BRAIN has thousands of data fields for you to create Alphas. But how do you quickly understand a new data field? Here are 6 ways. Simulate the below expressions in “None” neutralization and decay 0 setting. And obtains insights of specific parameters using the Long Count and Short Count in the IS Summary section of the results.


[TABLE 内容省略——图片/多媒体]

For example, if you simulate [close <= 0], You will see Long and Short Counts as 0. This implies that closing price always has a positive value (as expected!)

## Dataset Value Score (available for Consultants only)
Dataset Value Score is a measure which signifies underutilization of a dataset. Consultants are advised to research and make Alphas using datasets with a higher value score. Don't confuse this with Value Factor.

## Data Coverage
Coverage refers to the fraction of the total instruments present in the universe for which the given data field has a defined value. Low coverage fields can be handled by making use of backfill operators like ts_backfill, kth element, group_backfill, etc. Make use of the visualization feature to analyze the coverage of the data fields. Read this BRAIN Forum Post to know more about coverage handling.

## Further Resources
- Building Technical Indicators with Data Fields
- Finite Differences
- Statistics in Alpha Research
