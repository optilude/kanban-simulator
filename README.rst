Kanban Simulator
================

Helpers for running simulations of Kanban systems.

Currently no GUI, but works well in a Jupyter/iPython Notebook, like
(requires installation of `ipython[notebook]`, `pandas`, `numpy`,
`matplotlib` and `openpyxel`)::

    import random
    import kanban_simulator.board as kb

    # For rendering HTML output in an iPython notebook:
    from IPython.display import display, HTML
    %matplotlib inline

    # For data analysis and plan view:
    import pandas as pd
    import numpy as np

    def to_plan(board, start_date, finished_day, freq='W-MON'):
        """Use Pandas to print a week-by-week plan-like view showing
        what state each card was in each week.
        """

        grid = pd.DataFrame(
            index=[c.name for c in board.donelog.cards],
            columns=pd.date_range(start_date, freq='D', periods=finished_day)
        )

        for card in board.donelog.cards:
            for col, data in card.history.items():
                for day in data['dates']:
                    grid.ix[card.name, day-1] = col.name

        return grid.resample(freq, label='left', axis=1).first().fillna("")

    # Build a backlog with some epics.
    # Stipulate that when the epic enters the "Build" sublane-column, it will
    # split into a number of stories.

    backlog = kb.Backlog(cards=[
            kb.Epic("Epic one", splits={'Build': random.randint(5, 10)}),
            kb.Epic("Epic two", splits={'Build': random.randint(10, 20)}),
            kb.Epic("Epic three", splits={'Build': 30}),
            kb.Epic("Epic four", splits={'Build': 50}),
            kb.Epic("Epic five", splits={'Build': 50}),
            kb.Epic("Epic six", splits={'Build': 50}),
            kb.Epic("Epic seven", splits={'Build': 50}),
        ])

    # Create a lane and clone it so that we have two lanes with the same columns
    # It has a lane-wide WIP limit (optional), and a series of columns
    # operating on epics. The "Build" column has a sub-lane (or rather,
    # might have one or more depending on the number of epics in this column,
    # subject to WIP limits), which operates on stories. The epic itself splits
    # into stories and becomes a backlog for these stories, as per the number of
    # stories above.

    lane_template = kb.Lane(
        name="<lane name>",
        wip_limit=3,
        columns=[
            kb.Column(
                name="Discovery",
                touch=lambda: random.randint(5, 10),
                wip_limit=1,
                card_type=kb.Epic
            ),
            kb.QueueColumn(
                name="Ready for Build",
                wip_limit=1,
                card_type=kb.Epic
            ),
            kb.SublaneColumn(
                name="Build",
                lane_template=kb.Lane(
                    name="Build",
                    columns=[
                        kb.Column(
                            name="Analysis",
                            touch=lambda: random.randint(1, 3),
                            wip_limit=3,
                            card_type=kb.Story
                        ),
                        kb.Column(
                            name="Development",
                            touch=lambda: random.randint(1, 4),
                            wip_limit=3,
                            card_type=kb.Story
                        ),
                        kb.Column(
                            name="Test",
                            touch=lambda: random.randint(1, 2),
                            wip_limit=3,
                            card_type=kb.Story
                        ),
                    ],
                ),
                wip_limit=1,
                card_type=kb.Epic
            ),
            kb.Column(
                name="Final testing",
                touch=lambda: random.randint(1, 5),
                wip_limit=1,
                card_type=kb.Epic
            ),
        ]
    )

    lanes = [
        lane_template.clone(name="Team 1"),
        lane_template.clone(name="Team 2"),
    ]

    # Create the board
    board = kb.Board(
        name="Test simulation",
        lanes=lanes,
        backlog=backlog
    )

    # Show the Kanban board day by day. The board is a state machine,
    # so when we iterate through it, the state changes. We use `clone()` to
    # get a new copy so we can use the same `board` later.

    for day, board_state in board.clone():
        print "Day", day
        board_html = board_state.to_html()

        # iPython notebook specific magic to print HTML
        display(HTML(board_html))

    # If we only want the end state, we can just do:
    days, board_state = board.clone().run_simulation()
    print "It took", days, "days"

    # The cards are in the `board_state.donelog.cards` list. They have
    # attributes like `age` (total number of days), `dates` (dates the card
    # was active), `touch` (number of days actually working on a card, as
    # opposed to waiting), and `history` (a breakdown of `age`, `dates` and
    # `touch`) by column name.

    # We can also run a Monte Carlo simulation:
    mc_results = board.run_monte_carlo_simulation(trials=100)

    # We can do some data analysis on the finish dates of each
    finishes = pd.Series([r[0] for r in mc_results])

    print "Monte Carlo, after", len(mc_results), "loops. Quantiles:"
    print finishes.quantile([0.5, 0.85, 0.95])

    # Histogram of finishes
    finishes.plot.hist()

    # Board at the 85th percentile, output as a grid plan
    day85, board85 = mc_results[int(len(mc_results) * 0.85)]

    plan = to_plan(board85, '2016-06-01', day85)
    display(HTML(plan.to_html()))

    # Save to Excel (requires openpyxl)
    plan.to_excel("simulation.xlsx", "Simulation")


Changelog
---------

0.2 - 24 May 2016
    * Card `history` is now an OrderedDict
    * A backlog can now have a chained "parent" backlog via `card_source`

0.1 - 24 May 2016
    * Initial release
