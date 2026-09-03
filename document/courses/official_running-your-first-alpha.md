# Simulate your first Alpha

> 官方教程页（BRAIN /learn）：`running-your-first-alpha` | 类别：Getting Started | 时长：PT3M
> 来源：仓库调研素材 tutorial_pages.json（登录态抓取）| 用途：bootcamp 模块 M2 | 最后更新：2026-08-26

Alphas are created and simulated on the Simulate page in the Alphas dropdown tab. To run your first simulation, click on the gear icon at the top right-hand side corner. This will open the settings panel. Here, select “US: TOP3000” for Region and Universe, “Subindustry” for Neutralization and apply your settings. Make sure both Code and Result are ticked by clicking on them. In the Alpha expression text box, enter -Delta(close, 5) for now and click on "Simulate". The Simulation Result page will show a graph for Cumulative Profit. This graph can be zoomed in to plot area for shorter time periods (1 month or 1 year).

The display consists of 2 graphs, one for PnL vs. Time and the other for Sharpe Ratio vs. Time.
In the Stats tab, a good Alpha tend to have consistently increasing PnL and high Annual Return, Sharpe Ratio, % Profitable Days and Profit per Dollar Traded. It should have low Drawdown and Turnover. And more importantly, it shouldn’t have high fluctuations in the cumulative profit graph. If the standard deviation is low, there tends to be lesser fluctuations in the graph. If the graph shows high fluctuations/volatility, despite the returns being high, the Alpha will not be deemed good enough. An Alpha is considered to be “good” if:
- Its turnover is low, but not less than 1%
- Its Percentage Drawdown is less than 10%
- Its Sharpe is greater than 2.0 for delay 0 Alphas and greater than 1.25 for delay 1 Alphas
The graph above for Alpha expression -Delta(close, 5) shows several significant drawdowns, as well as a flattening of returns in 2017. The table below marks this Alpha as Inferior (Needs Improvement). PnL and Sharpe for 2017 drop low, and drawdown is large in 2014 and 2015. This Alpha is Inferior (Needs Improvement) due to high volatility and low returns.


[SIMULATION_EXAMPLE 内容省略——图片/多媒体]


[IMAGE 内容省略——图片/多媒体]

Use the green refreshing button in the Correlation block to get the information about the correlation of the currently simulated Alpha with the Alphas in your own OS (Out-of-Sample) pool. This will be explained further in the Simulation Results page.
The image below shows the Properties of the Alpha. You can name your Alpha, assign a category and color code, and add user-defined tags to them. You can add a brief description about your Alpha for your reference. Suggestion - keep the number of user-defined tags low so that they don't proliferate and are easily searchable in the My Alphas page.


[IMAGE 内容省略——图片/多媒体]

To Submit Alpha for OS Test, click the "Submit Alpha" button in the Submission tab of the results panel. This will check if the Alpha meets the Correlation and Sharpe criteria before submitting it.

Check out the below video for another example.
