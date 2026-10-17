"""hardHats crews - the work teams, each a few lines of config over the engine.

A crew is a line-up of hats. A hat is an LLM wearing an instruction, or a
deterministic gate. The house crew is all gates (the facts) with an optional
LLM foreman on the end (the judgement). Import one and run it:

    from hardhats.crews.house import house_crew
    outputs = house_crew("path/to/page.html").run("pre-publish")
"""
