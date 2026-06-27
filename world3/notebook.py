import marimo

__generated_with = "0.23.11"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # World3 Model

    This notebook implements the World3 model developed by Meadows [1], validated by Branderhorst [2], and implemented by Vanwynsberghe [3].
    """)
    return


@app.cell
def _(
    agriculture,
    capital,
    fundamentals,
    get_changed,
    load,
    mo,
    model,
    plot,
    references,
    save,
    scenario_file,
    scenario_name,
):
    # main ui
    mo.vstack([
        mo.ui.tabs(
            {
                "Scenario": mo.vstack(
                    [
                        mo.hstack([load, save, scenario_name], justify="start"),
                        scenario_file,
                    ]
                ),
                "Parameters": mo.ui.tabs(
                    {
                        "Fundamentals": fundamentals,
                        "Population": None,
                        "Resources": None,
                        "Agriculture": agriculture,
                        "Capital": capital,
                        "Pollution": None,
                    }
                ),
                "Results": mo.ui.tabs(
                    {
                        "Plot": plot,
                        "Table": mo.ui.table(
                            model.round(3),
                            page_size=20,
                        ),
                    }
                ),
                "References": references,
            }
        ),
        mo.md(f"----\n\nStatus: {get_changed()}"),
    ])
    return


@app.cell
def _(load_scenario, mo, save_scenario, scenario_file, scenario_name):
    # load/save buttons
    load = mo.ui.button(label="Load",on_click=load_scenario,disabled=len(scenario_file.value)==0)
    save = mo.ui.button(label="Save",on_click=save_scenario,disabled=len(scenario_name.value)==0)
    return load, save


@app.cell
def _(mo):
    # save state
    get_changed,set_changed = mo.state("Ready")
    return get_changed, set_changed


@app.cell
def _(mo, scenario_file):
    # scenario name
    scenario_name = mo.ui.text(value=scenario_file.name(0) if scenario_file.value else "unnamed.json")
    return (scenario_name,)


@app.cell
def _(mo):
    # scenario file
    scenario_file = mo.ui.file_browser(filetypes=[".json"], multiple=False)
    return (scenario_file,)


@app.cell
def _(json, mo, scenario_name, set_changed):
    # scenario data
    get_scenario,set_scenario = mo.state(None)
    def load_scenario(file="new.json"):
        if file is None: file = scenario_name.value
        try:
            with open(file,"r") as fh:
                set_scenario(json.load(fh))
            set_changed("Loaded")
        except Exception as err:
            set_changed(f"ERROR: {err}")

    def save_scenario(file=None):
        if file is None: file = scenario_name.value
        data = {x:globals()[x].value for x in [

            # fundamentals
            "plot_scales","year_min","year_max","timestep","pyear","verbose",

            # agriculture
            "ali","pali","lfh","palt","pl","alai1","alai2","io70","lyf1","lyf2",
            "sd","uili","alln","uildt","lferti","ilf","fspd","sfpc",

            # capital
            "ici","sci","iet","iopcd","lfpf","lufdt","icor1","icor2",
            "scor1","scor2","alic1","alic2","alsc1","alsc2","fioac1","fioac2",

            # pollution
            "ppoli","ppol70","ahl70","amti","imti","imef","frpm","ppgf1","ppgf1",
            "ppgf21","pptd1","pptd2","ppol","ppolx","ppgao","ppgio","ppgf","ppgr",
            "ppapr","ppasr","pptd","ahl","ahlm",

            ] if x in globals() and hasattr(globals()[x],"value")}
        with open(file,"w") as fh:
            json.dump(data,fh,indent=4)
        set_changed("Saved")
    load_scenario()
    return get_scenario, load_scenario, save_scenario


@app.cell
def _(
    World3,
    alai1,
    alai2,
    ali,
    alic1,
    alic2,
    alln,
    alsc1,
    alsc2,
    fioac1,
    fioac2,
    fspd,
    ici,
    icor1,
    icor2,
    iet,
    ilf,
    io70,
    iopcd,
    lferti,
    lfh,
    lfpf,
    lufdt,
    lyf1,
    lyf2,
    mo,
    pali,
    palt,
    pl,
    pyear,
    sci,
    scor1,
    scor2,
    sd,
    set_changed,
    sfpc,
    timestep,
    uildt,
    uili,
    verbose,
    year_max,
    year_min,
):
    ""# model data
    with mo.status.spinner("Running World3...") as _spinner:
        try:
            model = World3(

                # fundamentals
                year_min=year_min.value,
                year_max=year_max.value,
                dt=timestep.value,
                pyear=pyear.value,
                verbose=verbose.value,

                # agriculture (initial)
                ali=ali.value * 1e9,
                pali=pali.value * 1e9,
                lfh=lfh.value,
                palt=palt.value * 1e9,
                pl=pl.value,
                alai1=alai1.value,
                alai2=alai2.value,
                io70=io70.value * 1e12,
                lyf1=lyf1.value,
                lyf2=lyf2.value,
                sd=sd.value,
                uili=uili.value * 1e6,
                alln=alln.value * 1e3,
                uildt=uildt.value,
                lferti=lferti.value,
                ilf=ilf.value,
                fspd=fspd.value,
                sfpc=sfpc.value,

                # capital
                ici=ici.value * 1e12,
                sci=sci.value * 1e12,
                iet=iet.value,
                iopcd=iopcd.value,
                lfpf=lfpf.value,
                lufdt=lufdt.value,
                icor1=icor1.value,
                icor2=icor2.value,
                scor1=scor1.value,
                scor2=scor2.value,
                alic1=alic1.value,
                alic2=alic2.value,
                alsc1=alsc1.value,
                alsc2=alsc2.value,
                fioac1=fioac1.value,
                fioac2=fioac2.value,    

                # pollution
                # ppoli=ppoli.value * 1e6,
                # ppol70=ppol70.value * 1e9,
                # ahl70=ahl70.value,
                # amti=amti.value,
                # imti=imti.value,
                # imef=imef.value,
                # frpm=frpm.value,
                # ppgf1=ppgf1.value,
                # # ppgf1=ppgf1.value,
                # ppgf21=ppgf21.value,
                # pptd1=pptd1.value,
                # pptd2=pptd2.value,
                # ppol=ppol.value,
                # ppolx=ppolx.value,
                # ppgao=ppgao.value,
                # ppgio=ppgio.value,
                # ppgf=ppgf.value,
                # ppgr=ppgr.value,
                # ppapr=ppapr.value,
                # ppasr=ppasr.value,
                # pptd=pptd.value,
                # ahl=ahl.value,
                # ahlm=ahlm.value,
            )
            set_changed("Ok")
        except Exception as err:
            set_changed(f"ERROR: {err}")
            # model.index = pd.DatetimeIndex([dt.date(int(x),int((x-int(x))*12)+1,1) for x in model.index])
    return (model,)


@app.cell
def _():
    # pollution
    # ppoli = slider("Initial persistent pollution [GT]",0,1000,10,"ppoli") 
    # ppol70 = slider("Persistent pollution in {pyear.value:.0f}",0,1000,10,"ppol70")
    # ahl70 = slider()
    # amti = slider()
    # imti = slider()
    # imef = slider()
    # frpm = slider()
    # ppgf1 = slider()
    # ppgf1 = slider()
    # ppgf21 = slider()
    # pptd1 = slider()
    # pptd2 = slider()
    # ppol = slider()
    # ppolx = slider()
    # ppgao = slider()
    # ppgio = slider()
    # ppgf = slider()
    # ppgr = slider()
    # ppapr = slider()
    # ppasr = slider()
    # pptd = slider()
    # ahl = slider()
    # ahlm = slider()
    return


@app.cell
def _(mo, set_changed, year_max, year_min):
    # plot control
    plot_population = mo.ui.checkbox(label="Population",value=True)
    plot_resources = mo.ui.checkbox(label="Resources",value=True)
    plot_industry = mo.ui.checkbox(label="Industry",value=True)
    plot_agriculture = mo.ui.checkbox(label="Agriculture",value=True)
    plot_pollution = mo.ui.checkbox(label="Pollution",value=True)
    plot_peaks = mo.md("") # mo.ui.checkbox(label="Show peaks",value=True)
    plot_logy = mo.ui.checkbox(label="Log Y-scale",value=False)
    plot_scales = mo.ui.dropdown(label="Scale year",options=list(map(int,range(year_min.value,year_max.value,10))),value=year_min.value,on_change=set_changed)
    plots = mo.hstack([plot_population,plot_resources,plot_industry,plot_agriculture,plot_pollution,plot_peaks,plot_logy,plot_scales],justify='start')
    return (
        plot_agriculture,
        plot_industry,
        plot_logy,
        plot_pollution,
        plot_population,
        plot_resources,
        plot_scales,
        plots,
    )


@app.cell
def _(
    dt,
    mo,
    model,
    plot_agriculture,
    plot_industry,
    plot_logy,
    plot_pollution,
    plot_population,
    plot_resources,
    plot_scales,
    plots,
    plt,
    pyear,
):
    # results plot
    _colors = [
        ("population",plot_population,"b"),
        ("resources",plot_resources,"y"), 
        ("industry",plot_industry,"k"), 
        ("agriculture",plot_agriculture,"g"), 
        ("pollution",plot_pollution,"r"),
        ]
    _columns = [x for x,y,z in _colors if y.value]
    _color = {x:z for x,y,z in _colors if y.value}
    _data = model.scale(plot_scales.value)[[x for x,y,z in _colors if y.value]]
    _data.plot(
            grid=True,
            logy=plot_logy.value,
            figsize=(10, 7),
            ylabel=f"Value pu.{plot_scales.value}",
            xlabel="Year",
            color=_color,
        )
    _peaks = [float(_data[x].max(axis=0)) for x in _columns]
    plt.axvline(x=dt.date(pyear.value,1,1),color="k",linestyle="--",label="Policy year")
    plt.legend()
    plot=mo.vstack([plots,mo.mpl.interactive(plt.gca())])
    return (plot,)


@app.cell
def _(get_scenario, mo, set_changed, slider):
    # fundamentals
    year_min = slider("Starting year",1900,2000,10,"year_min")
    year_max = slider("Ending year",2000,2200,10,"year_max")
    timestep = mo.ui.slider(label="Time step (y)",steps=[0.1,0.25,0.5,1.0],value=get_scenario()["timestep"],debounce=True,show_value=True,on_change=lambda x:set_changed("Changed"))
    pyear = slider("Policy year",1950,2050,5,"pyear")
    verbose = mo.ui.checkbox(label="Verbose output",value=get_scenario()["verbose"],on_change=lambda x:set_changed("Changed"))

    fundamentals = mo.vstack([year_min,year_max,timestep,pyear,verbose])
    return fundamentals, pyear, timestep, verbose, year_max, year_min


@app.cell
def _(mo, pyear, slider):
    # agriculture
    ali = slider("Arable land (Gha)", 0.1, 2.0, 0.1, "ali")
    pali = slider("Potentially arable land (Gha)", 0.1, 4.0, 0.1, "pali")
    lfh = slider("Land fraction harvested (/unit)", 0.0, 1.0, 0.1, "lfh")
    palt = slider("Potentially arable land total [Gha]", 0.1, 5.0, 0.1, "palt")
    pl = slider("Processing loss (/unit)", 0.0, 1.0, 0.1, "pl")
    alai1 = slider(f"Average lifetime of agricultural inputs before {pyear.value} (y)", 0.5, 10, 0.5, "alai1")
    alai2 = slider(f"Average lifetime of agricultural inputs after {pyear.value} (y)", 0.5, 10, 0.5, "alai2")
    io70 = slider("Industrial output in 1970 ($T/y)", 0, 10, 0.01, "io70")
    lyf1 = slider("Land yield factor before policy year (/unit)", 0.1, 1, 0.1, "lyf1")
    lyf2 = slider("Land yield factor after policy year (/unit)", 0.1, 1, 0.1, "lyf2")
    sd = slider("Social discount (/y)", 0, 1, 0.01, "sd")
    uili = slider("Urban/industrial land (Mha)", 0, 100, 0.1, "uili")
    alln = slider("Average life of land normal (ky)", 0, 10, 1, "alln")
    uildt = slider("Urban-industrial land development time (y)", 1, 20, 1, "uildt")
    lferti = slider("Land fertility initial (kg/ha/y]", 0, 2000, 100, "lferti")
    ilf = slider("Inherent land fertility (kg/ha/y)", 0, 2000, 100, "ilf")
    fspd = slider("Food shortage perception delay (y)", 0, 10, 1, "fspd")
    sfpc = slider("Subsistence food per capita (kg/person/y)", 0, 1000, 10, "sfpc")

    agriculture = mo.vstack([ali,pali,lfh,palt,pl,alai1,alai2,io70,lyf1,lyf2,
                             sd,uili,alln,uildt,lferti,ilf,fspd,sfpc])
    return (
        agriculture,
        alai1,
        alai2,
        ali,
        alln,
        fspd,
        ilf,
        io70,
        lferti,
        lfh,
        lyf1,
        lyf2,
        pali,
        palt,
        pl,
        sd,
        sfpc,
        uildt,
        uili,
    )


@app.cell
def _(mo, pyear, slider):
    # capital
    ici = slider("Initial industrial capital ($T)", 0.01, 10.0, 0.01, "ici")
    sci = slider("Service capital ($T)", 0.01, 10.0, 0.01, "sci")
    iet = slider("Industrial equilibrium time (y)", 100, 10000, 100, "iet")
    iopcd = slider("Industrial output per capita desired ($/person/y)", 0, 10000, 100, "iopcd")
    lfpf = slider("Labor force participation factor (/unit)", 0, 1, 0.05, "lfpf")
    lufdt = slider("Labor utilization fraction delay time (y)", 0, 10, 1, "lufdt")
    icor1 = slider(f"Industrial capital-output ratio before {pyear.value} (y) ", 0.1, 10, 0.1, "icor1")
    icor2 = slider(f"Industrial capital-output ratio after {pyear.value} (y)", 0.1, 10, 0.1, "icor2")
    scor1 = slider(f"Service capital-output ratio before {pyear.value} (y)", 0.1, 10, 0.1, "scor1")
    scor2 = slider(f"Service capital-output ratio after {pyear.value} (y)", 0.1, 10, 0.1, "scor2")
    alic1 = slider(f"Average lifetime of industrial capital before {pyear.value} (y)", 1, 50, 1, "alic1")
    alic2 = slider(f"Average lifetime of industrial capital after {pyear.value} (y)", 1, 50, 1, "alic2")
    alsc1 = slider(f"Average lifetime of service capital before {pyear.value} (y)", 1, 50, 1, "alsc1")
    alsc2 = slider(f"Average lifetime of service capital after {pyear.value} (y)", 1, 50, 1, "alsc2")
    fioac1 = slider(f"Fraction of industrial output allocated to consumption before {pyear.value} (/unit)", 0, 1, 0.01, "fioac1")
    fioac2 = slider(f"Fraction of industrial output allocated to consumption after {pyear.value} (/unit)", 0, 1, 0.01, "fioac2")
    capital = mo.vstack([ici,sci,iet,iopcd,lfpf,lufdt,icor1,icor2,
                         scor1,scor2,alic1,alic2,alsc1,alsc2,fioac1,fioac2])
    return (
        alic1,
        alic2,
        alsc1,
        alsc2,
        capital,
        fioac1,
        fioac2,
        ici,
        icor1,
        icor2,
        iet,
        iopcd,
        lfpf,
        lufdt,
        sci,
        scor1,
        scor2,
    )


@app.cell(hide_code=True)
def _(mo):
    # references
    references=mo.md(r"""
    1. [Meadows, Donella H., Randers, Jorgen and Meadows, Dennis L.. "The Limits to
    Growth (1972)".](https://www.donellameadows.org/wp-content/userfiles/Limits-to-Growth-digital-scan-version.pdf)

    2. [Branderhorst, Gaya. 2020. Update to Limits to Growth: Comparing the World3
    Model With Empirical Data. Master's thesis, Harvard Extension School.](https://dash.harvard.edu/server/api/core/bitstreams/c5a728c0-e735-4bcf-bee8-b80ca370dbaf/content)

    3. [PyWorld3, GitHub (2021). Accessed May 12 2026.](https://github.com/cvanwynsberghe/pyworld3)
    """)
    return (references,)


@app.cell
def _(get_scenario, mo, set_changed):
    # sliders
    def slider(label, start, stop, step, value):
        return mo.ui.slider(
            start=start,
            stop=stop,
            step=step,
            label=label + ":",
            value=get_scenario()[value],
            show_value=True,
            debounce=True,
            on_change=lambda x:set_changed("Changed"),
        )

    return (slider,)


@app.cell
def _():
    # imports
    import marimo as mo
    import json
    import datetime as dt
    import control as cs
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from world3 import World3

    return World3, dt, json, mo, plt


if __name__ == "__main__":
    app.run()
