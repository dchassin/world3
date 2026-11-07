#!/usr/bin/env python3
"""
world3_abm.py -- Agent-based, finite-difference implementation of World3.

Design
------
* No ODE solver.  Every stock is advanced with an explicit forward difference
      x[k+1] = x[k] + dt * (inflow[k] - outflow[k])
  and every information/material delay (SMOOTH, SMOOTH3, DLINF3, DELAY3) is a
  cascade of first-order lags advanced with a difference equation
      s[k+1] = s[k] + dt/(tau + dt) * (u - s[k])
  which stays stable for any dt between 1 day and 1 year.
* Each World3 sector is an *agent* that owns its state variables, its
  parameters and its behavioural rules:

      CapitalAgent       industrial + service capital, output allocation, jobs
      AgricultureAgent   land, fertility, agricultural inputs, food
      PopulationAgent    four age cohorts, mortality, fertility
      PollutionAgent     persistent pollution generation / assimilation
      ResourceAgent      non-renewable resources

  Agents never touch each other's stocks; they read each other's *published*
  quantities (e.g. ``world.capital.IOPC``).
* Every tick runs three synchronous phases over all agents:
      sense()    compute auxiliaries from the current state
      act()      compute rates (flows) and delay inputs
      advance()  apply the finite-difference update
  so the update is a true simultaneous finite-difference step.
* Output is a pandas DataFrame: one row per timestep (DatetimeIndex), one
  column per state variable (plus optional diagnostic variables).

Usage
-----
    from world3_abm import World3ABM
    df = World3ABM(dt_days=365).run()          # annual steps
    df = World3ABM(dt_days=1).run()            # daily steps (slow, ~73k rows)
    df = World3ABM(dt_days=30).run(1900, 2100)

    python3 world3_abm.py --dt 1Y --out run.csv
"""
from __future__ import annotations

import argparse
import re
import time as _time
from typing import Dict, Iterable, List, Optional, Union

import pandas as pd

YEAR_DAYS = 365.2425          # length of a model year in days


# --------------------------------------------------------------------------- #
# Small numerical helpers
# --------------------------------------------------------------------------- #
class Table:
    """Piecewise-linear lookup on a uniform grid (DYNAMO's TABHL)."""

    __slots__ = ("x0", "dx", "y", "n")

    def __init__(self, x0: float, x1: float, y: Iterable[float]):
        self.y = [float(v) for v in y]
        self.n = len(self.y)
        self.x0 = float(x0)
        self.dx = (float(x1) - float(x0)) / (self.n - 1)

    def __call__(self, x: float) -> float:
        u = (x - self.x0) / self.dx
        if u <= 0.0:
            return self.y[0]
        if u >= self.n - 1:
            return self.y[-1]
        i = int(u)
        return self.y[i] + (u - i) * (self.y[i + 1] - self.y[i])

    def slope(self, x: float) -> float:
        """d(table)/dx -- used for marginal productivities."""
        u = (x - self.x0) / self.dx
        if u < 0.0 or u >= self.n - 1:
            return 0.0
        i = int(u)
        return (self.y[i + 1] - self.y[i]) / self.dx


class Lag:
    """Cascade of ``order`` first-order lags with total delay ``tau`` years.

    order=1 -> SMOOTH ;  order=3 -> SMOOTH3 / DLINF3 / DELAY3.
    """

    __slots__ = ("tau", "order", "s")

    def __init__(self, tau: float, order: int = 1, init: float = 0.0):
        self.tau = float(tau)
        self.order = order
        self.s = [float(init)] * order

    @property
    def out(self) -> float:
        return self.s[-1]

    def reset(self, x: float) -> None:
        self.s = [float(x)] * self.order

    def step(self, u: float, dt: float) -> None:
        a = dt / (self.tau / self.order + dt)
        for i in range(self.order):
            self.s[i] += a * (u - self.s[i])
            u = self.s[i]


def default_tables() -> Dict[str, Table]:
    """Nonlinear functions of World3-03 (as used in PyWorld3)."""
    T = Table
    return dict(
        # --- population ---------------------------------------------------
        m1=T(20, 80, [.0567, .0366, .0243, .0155, .0082, .0023, .0010]),
        m2=T(20, 80, [.0266, .0171, .0110, .0065, .0040, .0016, .0008]),
        m3=T(20, 80, [.0562, .0373, .0252, .0171, .0118, .0083, .0060]),
        m4=T(20, 80, [.1300, .1100, .0900, .0700, .0600, .0500, .0400]),
        lmf=T(0, 5, [0, 1, 1.43, 1.5, 1.5, 1.5]),
        hsapc=T(0, 2000, [0, 20, 50, 95, 140, 175, 200, 220, 230]),
        lmhs1=T(0, 100, [1, 1.1, 1.4, 1.6, 1.7, 1.8]),
        lmhs2=T(0, 100, [1, 1.4, 1.6, 1.8, 1.95, 2.0]),
        lmp=T(0, 100, [1, .99, .97, .95, .90, .85, .75, .65, .55, .40, .20]),
        cmi=T(0, 1600, [.5, .05, -.1, -.08, -.02, .05, .1, .15, .2]),
        fpu=T(0, 16e9, [0, .2, .4, .5, .58, .65, .72, .78, .80]),
        fm=T(0, 80, [0, .2, .4, .6, .8, .9, 1.0, 1.05, 1.1]),
        cmple=T(0, 70, [3.0, 2.1, 1.6, 1.4, 1.3, 1.2, 1.1, 1.05]),
        frsn=T(-.2, .2, [.5, .6, .7, .85, 1.0]),
        sfsn=T(0, 800, [1.25, .94, .715, .585, .5]),
        fsafc=T(0, 10, [0, .005, .015, .025, .03, .035]),
        fce=T(0, 3, [.75, .85, .90, .95, .98, .99, 1.0]),
        # --- capital ------------------------------------------------------
        fcaor=T(0, 1, [1, .9, .7, .5, .2, .1, .05, .05, .05, .05, .05]),
        fioas=T(0, 2, [.3, .2, .1, .05, .05]),
        isopc=T(0, 1600, [40, 300, 640, 1000, 1220, 1450, 1650, 1800, 2000]),
        fioacv=T(0, 2, [.3, .32, .34, .36, .38, .43, .73, .77, .81, .82, .83]),
        jpicu=T(50, 800, [.37, .18, .12, .09, .07, .06]),
        jpscu=T(50, 800, [1.1, .6, .35, .2, .15, .15]),
        jph=T(2, 22, [2, .5, .4, .3, .27, .24]),
        cuf=T(1, 11, [1, .9, .7, .3, .1, .1]),
        # --- agriculture --------------------------------------------------
        ifpc=T(0, 1600, [230, 480, 690, 850, 970]),
        fioaa=T(0, 2.5, [.4, .2, .1, .025, 0, 0]),
        lymc=T(0, 1000, [1, 3, 3.8, 4.4, 4.9, 5.4, 5.7, 6, 6.3, 6.6, 6.9, 7.2,
                         7.4, 7.6, 7.8, 8, 8.2, 8.4, 8.6, 8.8, 9, 9.2, 9.4,
                         9.6, 9.8, 10]),
        lymap1=T(0, 30, [1, 1, .7, .4]),
        lymap2=T(0, 30, [1, 1, .98, .95]),
        dcph=T(0, 1, [100000, 7400, 5200, 3500, 2400, 1500, 750, 300, 150,
                      75, 50]),
        fiald=T(0, 2, [0, .05, .15, .30, .50, .70, .85, .95, 1.0]),
        falm=T(0, 4, [0, .04, .07, .09, .10]),
        lfrt=T(0, .04, [20, 13, 8, 4, 2]),
        lfdr=T(0, 30, [0, .1, .3, .5]),
        uilpc=T(0, 1600, [.005, .008, .015, .025, .04, .055, .07, .08, .09]),
        llmy1=T(0, 9, [1.2, 1, .63, .36, .16, .055, .04, .025, .015, .01]),
        llmy2=T(0, 9, [1.2, 1, .63, .36, .29, .26, .24, .20, .20, .20]),
        # --- pollution / resources ---------------------------------------
        pcrum=T(0, 1600, [0, .85, 2.6, 4.4, 5.4, 6.2, 6.8, 7, 7]),
        ahlm=T(1, 1001, [1, 11, 21, 31, 41]),
    )


def default_params() -> Dict[str, float]:
    """World3-03 constants and initial conditions."""
    return dict(
        # initial conditions (state variables) ---------------------------
        p1i=65e7, p2i=70e7, p3i=19e7, p4i=6e7,       # population cohorts
        ici=2.1e11, sci=1.44e11,                      # industrial/service capital
        ali=0.9e9, pali=2.3e9, uili=8.2e6,            # land [ha]
        lferti=600.0, ai_i=5e9,                       # fertility, ag inputs
        pfri=1.0, lufi=1.0,                           # perceived food ratio, LUFD
        ppoli=2.5e7, nri=1e12,                        # pollution, resources
        # population ------------------------------------------------------
        len=28.0, mtfn=12.0, dcfsn=3.8, rlt=30.0, lpd=20.0, ieat=3.0,
        sad=20.0, hsid=20.0, iphst=1940.0, pet=4000.0, zpgt=4000.0,
        fcest=4000.0, mat1_yrs=15.0, mat2_yrs=30.0, mat3_yrs=20.0,
        # capital ---------------------------------------------------------
        icor1=3.0, icor2=3.0, scor1=1.0, scor2=1.0,
        alic1=14.0, alic2=14.0, alsc1=20.0, alsc2=20.0,
        fioacc=0.43, iopcd=400.0, lfpf=0.75, lufdt=2.0,
        # agriculture -----------------------------------------------------
        alai1=2.0, alai2=2.0, lyf1=1.0, lyf2=1.0, lfh=0.7, pl=0.1,
        ilf=600.0, sfpc=230.0, fspd=2.0, palt=3.2e9,
        alln=6000.0, uildt=10.0, io70=7.9e11,
        # pollution -------------------------------------------------------
        frpm=0.02, imef=0.1, imti=10.0, fipm=0.001, amti=1.0,
        pptd=20.0, ahl70=1.5, ppol70=1.36e8, ppgf1=1.0, ppgf2=1.0,
        # resources -------------------------------------------------------
        nruf1=1.0, nruf2=1.0,
        # policy switch year ---------------------------------------------
        pyear=1975.0,
    )


# --------------------------------------------------------------------------- #
# Agent base class
# --------------------------------------------------------------------------- #
class Agent:
    """A World3 sector.  Subclasses implement sense / act / advance."""

    name = "agent"

    def __init__(self, world: "World"):
        self.w = world
        self.p = world.p
        self.T = world.T
        self.aux: Dict[str, float] = {}

    # state variables exposed to the output DataFrame
    def states(self) -> Dict[str, float]:
        return {}

    # lags whose input must be (re)initialised to steady state
    def lags_to_steady(self):
        return []

    def sense(self) -> None: ...
    def act(self) -> None: ...
    def advance(self, dt: float) -> None: ...


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #
class ResourceAgent(Agent):
    name = "resources"

    def __init__(self, world):
        super().__init__(world)
        self.NR = self.p["nri"]
        self.NRUR = 0.0

    @property
    def NRFR(self) -> float:
        return self.NR / self.p["nri"]

    def states(self):
        return {"NR": self.NR}

    def sense(self):
        w, p = self.w, self.p
        nruf = p["nruf2"] if w.t >= p["pyear"] else p["nruf1"]
        self.NRUR = w.capital.PCRUM * w.population.POP * nruf
        self.aux = {"NRFR": self.NRFR, "NRUR": self.NRUR}

    def advance(self, dt):
        self.NR = max(0.0, self.NR - dt * self.NRUR)


# --------------------------------------------------------------------------- #
# Capital
# --------------------------------------------------------------------------- #
class CapitalAgent(Agent):
    name = "capital"

    def __init__(self, world):
        super().__init__(world)
        p = self.p
        self.IC, self.SC = p["ici"], p["sci"]
        self.LUFD = Lag(p["lufdt"], 3, p["lufi"])
        self.IO = self.SO = self.IOPC = self.SOPC = self.PCRUM = 0.0
        self.FIOAA = self.FIOAS = self.FIOAC = self.FIOAI = 0.0
        self.ICIR = self.ICDR = self.SCIR = self.SCDR = self.LUF = 0.0

    def states(self):
        return {"IC": self.IC, "SC": self.SC, "LUFD": self.LUFD.out}

    def sense(self):
        w, p, T = self.w, self.p, self.T
        icor = w.policy(p["icor1"], p["icor2"])
        scor = w.policy(p["scor1"], p["scor2"])
        fcaor = T["fcaor"](w.resources.NRFR)
        cuf = T["cuf"](self.LUFD.out)
        pop = w.population.POP
        self.IO = self.IC * (1.0 - fcaor) * cuf / icor
        self.SO = self.SC * cuf / scor
        self.IOPC = self.IO / pop
        self.SOPC = self.SO / pop
        self.PCRUM = T["pcrum"](self.IOPC)
        self.aux = {"IO": self.IO, "SO": self.SO, "IOPC": self.IOPC,
                    "SOPC": self.SOPC, "FCAOR": fcaor, "CUF": cuf,
                    "PCRUM": self.PCRUM}

    def act(self):
        w, p, T = self.w, self.p, self.T
        pop = w.population
        agr = w.agriculture
        # --- allocation of industrial output ---------------------------
        ifpc = T["ifpc"](self.IOPC)
        self.FIOAA = T["fioaa"](agr.FPC / ifpc)
        isopc = T["isopc"](self.IOPC)
        self.FIOAS = T["fioas"](self.SOPC / isopc)
        if w.t >= p["pyear"]:
            self.FIOAC = T["fioacv"](self.IOPC / p["iopcd"])
        else:
            self.FIOAC = p["fioacc"]
        self.FIOAI = max(0.0, 1.0 - self.FIOAA - self.FIOAS - self.FIOAC)
        alic = w.policy(p["alic1"], p["alic2"])
        alsc = w.policy(p["alsc1"], p["alsc2"])
        self.ICIR = self.IO * self.FIOAI
        self.ICDR = self.IC / alic
        self.SCIR = self.IO * self.FIOAS
        self.SCDR = self.SC / alsc
        # --- jobs and labour utilisation -------------------------------
        lf = (pop.P2 + pop.P3) * p["lfpf"]
        pjis = self.IC * T["jpicu"](self.IOPC) / 1000.0
        pjss = self.SC * T["jpscu"](self.SOPC) / 1000.0
        pjas = T["jph"](agr.AIPH) * agr.AL
        jobs = pjis + pjss + pjas
        self.LUF = lf / jobs if jobs > 0 else 1.0
        self.aux.update({"FIOAA": self.FIOAA, "FIOAS": self.FIOAS,
                         "FIOAC": self.FIOAC, "FIOAI": self.FIOAI,
                         "LF": lf, "JOBS": jobs, "LUF": self.LUF})

    def advance(self, dt):
        self.IC = max(0.0, self.IC + dt * (self.ICIR - self.ICDR))
        self.SC = max(0.0, self.SC + dt * (self.SCIR - self.SCDR))
        self.LUFD.step(self.LUF, dt)


# --------------------------------------------------------------------------- #
# Agriculture
# --------------------------------------------------------------------------- #
class AgricultureAgent(Agent):
    name = "agriculture"

    def __init__(self, world):
        super().__init__(world)
        p = self.p
        self.AL, self.PAL, self.UIL = p["ali"], p["pali"], p["uili"]
        self.LFERT = p["lferti"]
        self.AI = Lag(p["alai1"], 1, p["ai_i"])
        self.PFR = Lag(p["fspd"], 3, p["pfri"])
        self.AIPH = self.LY = self.F = self.FPC = 0.0
        self.LDR = self.LER = self.LRUI = self.LFR = self.LFD = 0.0
        self.CAI = 0.0

    def states(self):
        return {"AL": self.AL, "PAL": self.PAL, "UIL": self.UIL,
                "LFERT": self.LFERT, "AI": self.AI.out, "PFR": self.PFR.out}

    def lags_to_steady(self):
        return []                       # AI/PFR use their specified ICs

    def sense(self):
        w, p, T = self.w, self.p, self.T
        pop = w.population.POP
        self.FALM = T["falm"](self.PFR.out)
        self.AIPH = self.AI.out * (1.0 - self.FALM) / self.AL
        self.LYMC = T["lymc"](self.AIPH)
        ratio = w.capital.IO / p["io70"]
        lymap = (T["lymap2"] if w.t >= p["pyear"] else T["lymap1"])(ratio)
        lyf = w.policy(p["lyf1"], p["lyf2"])
        self.LY = lyf * self.LFERT * self.LYMC * lymap
        self.F = self.LY * self.AL * p["lfh"] * (1.0 - p["pl"])
        self.FPC = self.F / pop
        self.FR = self.FPC / p["sfpc"]
        self.aux = {"LY": self.LY, "F": self.F, "FPC": self.FPC,
                    "AIPH": self.AIPH, "FALM": self.FALM, "LYMC": self.LYMC,
                    "LYMAP": lymap}

    def act(self):
        w, p, T = self.w, self.p, self.T
        cap, pop, pol = w.capital, w.population, w.pollution
        tai = cap.IO * cap.FIOAA                       # total ag investment
        dcph = T["dcph"](self.PAL / p["palt"])
        mpld = self.LY / (dcph * p["sfpc"])
        alai = w.policy(p["alai1"], p["alai2"])
        mpai = alai * self.LY * T["lymc"].slope(self.AIPH) / self.LYMC
        ratio = mpld / mpai if mpai > 1e-12 else 1e6
        fiald = T["fiald"](ratio)
        self.LDR = tai * fiald / dcph
        self.CAI = tai * (1.0 - fiald)
        llmy = (T["llmy2"] if w.t >= p["pyear"] else T["llmy1"])(self.LY / p["ilf"])
        self.LER = self.AL / (p["alln"] * llmy)
        uilr = T["uilpc"](cap.IOPC) * pop.POP
        self.LRUI = max(0.0, (uilr - self.UIL) / p["uildt"])
        self.LFR = (p["ilf"] - self.LFERT) / T["lfrt"](self.FALM)
        self.LFD = self.LFERT * T["lfdr"](pol.PPOLX)
        self.aux.update({"TAI": tai, "FIALD": fiald, "LDR": self.LDR,
                         "LER": self.LER, "LRUI": self.LRUI, "DCPH": dcph})

    def advance(self, dt):
        ldr = min(self.LDR, self.PAL / dt)             # cannot exceed PAL
        self.AL = max(1.0, self.AL + dt * (ldr - self.LER - self.LRUI))
        self.PAL = max(0.0, self.PAL - dt * ldr)
        self.UIL += dt * self.LRUI
        self.LFERT = max(0.0, self.LFERT + dt * (self.LFR - self.LFD))
        self.AI.tau = self.w.policy(self.p["alai1"], self.p["alai2"])
        self.AI.step(self.CAI, dt)
        self.PFR.step(self.FR, dt)


# --------------------------------------------------------------------------- #
# Population
# --------------------------------------------------------------------------- #
class PopulationAgent(Agent):
    name = "population"

    def __init__(self, world):
        super().__init__(world)
        p = self.p
        self.P1, self.P2, self.P3, self.P4 = p["p1i"], p["p2i"], p["p3i"], p["p4i"]
        self.PLE = Lag(p["lpd"], 3, 30.0)
        self.AIOPC = Lag(p["ieat"], 1, 40.0)
        self.DIOPC = Lag(p["sad"], 3, 40.0)
        self.EHSPC = Lag(p["hsid"], 3, 0.0)
        self.FCFPC = Lag(p["hsid"], 3, 0.0)
        self.LE = 30.0
        self.B = self.D = 0.0
        self._rates = (0, 0, 0, 0)
        self._in = {}

    @property
    def POP(self) -> float:
        return self.P1 + self.P2 + self.P3 + self.P4

    def states(self):
        return {"P1": self.P1, "P2": self.P2, "P3": self.P3, "P4": self.P4,
                "PLE": self.PLE.out, "AIOPC": self.AIOPC.out,
                "DIOPC": self.DIOPC.out, "EHSPC": self.EHSPC.out,
                "FCFPC": self.FCFPC.out}

    def lags_to_steady(self):
        return [("PLE", self.PLE), ("AIOPC", self.AIOPC),
                ("DIOPC", self.DIOPC), ("EHSPC", self.EHSPC),
                ("FCFPC", self.FCFPC)]

    def sense(self):
        w, p, T = self.w, self.p, self.T
        cap, agr, pol = w.capital, w.agriculture, w.pollution
        pop = self.POP
        iopc, sopc = cap.IOPC, cap.SOPC
        # ---- life expectancy -------------------------------------------
        lmf = T["lmf"](agr.FPC / p["sfpc"])
        hsapc = T["hsapc"](sopc)
        ehspc = self.EHSPC.out
        lmhs = (T["lmhs2"] if w.t >= p["iphst"] else T["lmhs1"])(ehspc)
        lmp = T["lmp"](pol.PPOLX)
        lmc = 1.0 - T["cmi"](iopc) * T["fpu"](pop)
        le = p["len"] * lmf * lmhs * lmp * lmc
        self.LE = le
        # ---- mortality -------------------------------------------------
        m1, m2, m3, m4 = T["m1"](le), T["m2"](le), T["m3"](le), T["m4"](le)
        d1, d2, d3, d4 = self.P1 * m1, self.P2 * m2, self.P3 * m3, self.P4 * m4
        mat1 = self.P1 * (1 - m1) / p["mat1_yrs"]
        mat2 = self.P2 * (1 - m2) / p["mat2_yrs"]
        mat3 = self.P3 * (1 - m3) / p["mat3_yrs"]
        self.D = d1 + d2 + d3 + d4
        # ---- fertility -------------------------------------------------
        mtf = p["mtfn"] * T["fm"](le)
        cmple = T["cmple"](self.PLE.out)
        fie = (iopc - self.AIOPC.out) / self.AIOPC.out
        frsn = T["frsn"](fie)
        sfsn = T["sfsn"](self.DIOPC.out)
        dcfs = 2.0 if w.t >= p["zpgt"] else p["dcfsn"] * frsn * sfsn
        dtf = dcfs * cmple
        nfc = mtf / dtf - 1.0
        fcapc = T["fsafc"](nfc) * sopc
        fce = 1.0 if w.t >= p["fcest"] else T["fce"](self.FCFPC.out)
        tf = min(mtf, mtf * (1.0 - fce) + dtf * fce)
        self.TF = tf
        self.B = self.D if w.t >= p["pet"] else tf * self.P2 * 0.5 / p["rlt"]
        self._rates = (self.B - d1 - mat1, mat1 - d2 - mat2,
                       mat2 - d3 - mat3, mat3 - d4)
        self._in = {"PLE": le, "AIOPC": iopc, "DIOPC": iopc,
                    "EHSPC": hsapc, "FCFPC": fcapc}
        self.aux = {"POP": pop, "LE": le, "B": self.B, "D": self.D,
                    "TF": tf, "CBR": 1000 * self.B / pop,
                    "CDR": 1000 * self.D / pop, "LMF": lmf, "LMHS": lmhs,
                    "LMP": lmp, "LMC": lmc, "DTF": dtf, "MTF": mtf,
                    "HSAPC": hsapc, "FCAPC": fcapc}

    def advance(self, dt):
        r1, r2, r3, r4 = self._rates
        self.P1 = max(0.0, self.P1 + dt * r1)
        self.P2 = max(0.0, self.P2 + dt * r2)
        self.P3 = max(0.0, self.P3 + dt * r3)
        self.P4 = max(0.0, self.P4 + dt * r4)
        for key, lag in (("PLE", self.PLE), ("AIOPC", self.AIOPC),
                         ("DIOPC", self.DIOPC), ("EHSPC", self.EHSPC),
                         ("FCFPC", self.FCFPC)):
            lag.step(self._in[key], dt)


# --------------------------------------------------------------------------- #
# Persistent pollution
# --------------------------------------------------------------------------- #
class PollutionAgent(Agent):
    name = "pollution"

    def __init__(self, world):
        super().__init__(world)
        p = self.p
        self.PPOL = p["ppoli"]
        self.PPAPR = Lag(p["pptd"], 3, 1e7)
        self.PPGR = self.PPASR = 0.0

    @property
    def PPOLX(self) -> float:
        return self.PPOL / self.p["ppol70"]

    def states(self):
        return {"PPOL": self.PPOL, "PPAPR": self.PPAPR.out}

    def lags_to_steady(self):
        return [("PPGR", self.PPAPR)]

    def sense(self):
        w, p, T = self.w, self.p, self.T
        cap, agr = w.capital, w.agriculture
        ppgio = cap.PCRUM * w.population.POP * p["frpm"] * p["imef"] * p["imti"]
        ppgao = agr.AIPH * agr.AL * p["fipm"] * p["amti"]
        ppgf = w.policy(p["ppgf1"], p["ppgf2"])
        self.PPGR = (ppgio + ppgao) * ppgf
        ahl = p["ahl70"] * T["ahlm"](self.PPOLX)
        self.PPASR = self.PPOL / (ahl * 1.4)
        self.aux = {"PPOLX": self.PPOLX, "PPGR": self.PPGR,
                    "PPASR": self.PPASR, "AHL": ahl}

    def advance(self, dt):
        self.PPOL = max(0.0, self.PPOL + dt * (self.PPAPR.out - self.PPASR))
        self.PPAPR.step(self.PPGR, dt)


# --------------------------------------------------------------------------- #
# World: schedules the agents
# --------------------------------------------------------------------------- #
class World:
    def __init__(self, params, tables):
        self.p = params
        self.T = tables
        self.t = 0.0
        self.resources = ResourceAgent(self)
        self.capital = CapitalAgent(self)
        self.agriculture = AgricultureAgent(self)
        self.population = PopulationAgent(self)
        self.pollution = PollutionAgent(self)
        # sense/act order respects the information dependencies of World3
        self.agents: List[Agent] = [self.capital, self.agriculture,
                                    self.population, self.pollution,
                                    self.resources]

    def policy(self, v1: float, v2: float) -> float:
        """CLIP(v2, v1, TIME, PYEAR)."""
        return v2 if self.t >= self.p["pyear"] else v1

    def tick_phases(self):
        for a in self.agents:
            a.sense()
        for a in self.agents:
            a.act()

    def initialise(self, t0: float, passes: int = 6):
        """Start from World3 initial conditions; put delays in steady state
        (output = input) except those with specified initial values."""
        self.t = t0
        for _ in range(passes):
            self.tick_phases()
            pop = self.population
            for key, lag in pop.lags_to_steady():
                lag.reset(pop._in[key])
            self.pollution.PPAPR.reset(self.pollution.PPGR)

    def advance(self, dt: float):
        for a in self.agents:
            a.advance(dt)


# --------------------------------------------------------------------------- #
# Public simulation class
# --------------------------------------------------------------------------- #
def parse_dt(dt: Union[int, float, str]) -> float:
    """Timestep in days.  Accepts a number of days or strings such as
    '1D', '7D', '1W', '1M', '3M', '1Q', '1Y'."""
    if isinstance(dt, (int, float)):
        return float(dt)
    m = re.fullmatch(r"\s*([0-9.]+)\s*([DWMQY])\s*", dt.upper())
    if not m:
        raise ValueError(f"cannot parse timestep {dt!r}")
    n, unit = float(m.group(1)), m.group(2)
    return n * {"D": 1.0, "W": 7.0, "M": YEAR_DAYS / 12, "Q": YEAR_DAYS / 4,
                "Y": YEAR_DAYS}[unit]


class World3ABM:
    """Agent-based finite-difference World3.

    Parameters
    ----------
    dt_days : timestep in days, 1 <= dt_days <= 365.25 (or '1D'...'1Y').
    params  : overrides for ``default_params()`` (constants / initial values).
    tables  : overrides for ``default_tables()`` (name -> Table).
    """

    def __init__(self, dt_days: Union[int, float, str] = 365.25,
                 params: Optional[Dict[str, float]] = None,
                 tables: Optional[Dict[str, Table]] = None):
        self.dt_days = parse_dt(dt_days)
        if not 1.0 <= self.dt_days <= YEAR_DAYS:
            raise ValueError("timestep must be between 1 day and 1 year")
        self.dt = self.dt_days / YEAR_DAYS            # model years
        self.params = {**default_params(), **(params or {})}
        self.tables = {**default_tables(), **(tables or {})}

    def run(self, start_year: float = 1900, end_year: float = 2100,
            record: str = "all", start_date: Optional[str] = None
            ) -> pd.DataFrame:
        """Run the simulation.

        record = 'states' -> only state variables as columns
                 'all'    -> states + diagnostic/auxiliary variables
        Returns a DataFrame indexed by timestamp (one row per timestep).
        """
        world = World(self.params, self.tables)
        world.initialise(float(start_year))
        n = int(round((end_year - start_year) * YEAR_DAYS / self.dt_days))
        t0 = pd.Timestamp(start_date or f"{int(start_year):04d}-01-01")

        rows: List[List[float]] = []
        cols: List[str] = []
        for k in range(n + 1):
            world.t = start_year + k * self.dt_days / YEAR_DAYS
            world.tick_phases()
            rec: Dict[str, float] = {}
            for a in world.agents:
                rec.update(a.states())
            if record == "all":
                for a in world.agents:
                    rec.update(a.aux)
            if not cols:
                cols = list(rec)
            rows.append([rec[c] for c in cols])
            if k < n:
                world.advance(self.dt)

        index = pd.DatetimeIndex(
            [t0 + pd.Timedelta(seconds=round(k * self.dt_days * 86400))
             for k in range(n + 1)],
            name="time")
        df = pd.DataFrame(rows, index=index, columns=cols)
        df.attrs.update(dt_days=self.dt_days, start_year=start_year,
                        end_year=end_year)
        return df


# --------------------------------------------------------------------------- #
def main(argv=None):
    if argv is None and len(sys.argv) > 1:
        argv = sys.argv[1:]
    ap = argparse.ArgumentParser(description="Agent-based World3")
    ap.add_argument("--dt", default="1Y", help="timestep: days or 1D/1W/1M/1Y")
    ap.add_argument("--start", type=float, default=1900)
    ap.add_argument("--end", type=float, default=2100)
    ap.add_argument("--record", choices=["states", "all"], default="all")
    ap.add_argument("--out", help="write to .csv or .parquet")
    a = ap.parse_args(argv)

    t = _time.time()
    df = World3ABM(a.dt).run(a.start, a.end, a.record)
    # print(f"{len(df)} steps x {df.shape[1]} columns in {_time.time()-t:.1f}s")
    # print(df[show].iloc[:: max(1, len(df) // 20)])
    if a.out:
        (df.to_parquet if a.out.endswith(".parquet") else df.to_csv)(a.out)
        # print("wrote", a.out)
    return df


if __name__ == "__main__":

    pd.options.display.width = None
    pd.options.display.max_columns = None
    pd.options.display.max_rows = None

    df = main(["--dt","1M"])
    show = [c for c in ("POP", "NRFR", "IOPC", "FPC", "PPOLX", "LE") if c in df]
    print(df[show].resample("1YE").mean())
    # fig = df[show].plot()
    # fig.savefig("world3_abm.png")
