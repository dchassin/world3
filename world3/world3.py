"""World 3 model

Example
-------

The following python script runs the World3 model with dt=0.5

    from world3 import World3
    data = World3(dt=0.5)
    print(data)

and outputs the following

                  population  resources   industry  agriculture  pollution
    1900-01-01  1.600000e+09   1.000000  41.562500   269.325000   0.183824
    1900-07-01  1.603619e+09   0.999859  41.590900   282.194075   0.145820
    1901-01-01  1.607768e+09   0.999717  42.505344   279.977460   0.116865
    1901-07-01  1.612884e+09   0.999572  43.345727   278.943480   0.094805
    1902-01-01  1.618724e+09   0.999423  44.132665   278.612069   0.078010
    ...                  ...        ...        ...          ...        ...
    2098-01-01  4.036647e+09   0.152412  11.794787   233.659977   0.668423
    2098-07-01  4.021573e+09   0.152311  11.513758   234.163727   0.651181
    2099-01-01  4.006580e+09   0.152212  11.239519   234.679782   0.634348
    2099-07-01  3.991667e+09   0.152117  10.971905   235.208018   0.617912
    2100-01-01  3.976858e+09   0.152024  10.710687   235.746828   0.601865

    [401 rows x 5 columns]

"""
import datetime
import pandas as pd
import numpy as np
import pyworld3 as w3

class World3(pd.DataFrame):
    """World 3 model implementation"""

    SCALES = {
            "population":9,
            "resources":0,
            "industry":2,
            "agriculture":2,
            "pollution":1,
        }
    def __init__(self,
        year_min:int=1900,
        year_max:int=2100,
        dt:float=1,
        pyear:int=1975,
        verbose:bool=False,
        **kwargs):
        """Construct and solve the World3 model

        Arguments
        ---------
        - `year_min`: starting year
        - `year_max`: ending yeaer
        - `dt`: timestep
        - `pyear`: policy start year
        - `verbose`: enable verbose output
        - `scales`: scaling of data
        - `kwargs`: model constants

        Description
        -----------
        """

        world3 = w3.World3(
            year_min=year_min,
            year_max=year_max,
            dt=dt,
            pyear=pyear,
            verbose=verbose,
            )                    # choose the time limits and step.
        world3.init_world3_constants(**kwargs)       # choose the model constants.
        world3.init_world3_variables()       # initialize all variables.
        world3.set_world3_table_functions()  # get tables from a json file.
        world3.set_world3_delay_functions()  # initialize delay functions.
        world3.run_world3()
        df = pd.DataFrame(
            data={
                "population": world3.pop,
                "resources": world3.nrfr,
                "industry": world3.iopc,
                "agriculture": world3.fpc,
                "pollution": world3.ppolx,
            },
            index=pd.DatetimeIndex([datetime.date(year=int(x),month=int((x-int(x))*12)+1,day=1) for x in world3.time])
            )

        super().__init__(df)

    def scale(self,scales:float|dict=None):
        if scales is None:
            scales = self.SCALES

        if isinstance(scales,(int,float)):
            # print(f"{scales=}: {np.where(self.index.year==int(scales))[0]=}")
            scales = f"{int(scales)}-01-01"
            scales = {
                "population":np.log10(self.population.loc[scales]),
                "resources":np.log10(self.resources.loc[scales]),
                "industry":np.log10(self.industry.loc[scales]),
                "agriculture":np.log10(self.agriculture.loc[scales]),
                "pollution":np.log10(self.pollution.loc[scales]),
            }

        df = pd.DataFrame(
            data={
                "population": self.population / np.pow(10,scales["population"]),
                "resources": self.resources / np.pow(10,scales["resources"]),
                "industry": self.industry / np.pow(10,scales["industry"]),
                "agriculture": self.agriculture / np.pow(10,scales["agriculture"]),
                "pollution": self.pollution / np.pow(10,scales["pollution"]),
            },
            index=self.index,
            )
        return df


if __name__ == "__main__":

    import matplotlib.pyplot as plt
    
    test = World3().scale()
    print(World3.SCALES)
    test.columns = [fr"{x.title()} ($\times 10^{y}$)" for x,y in zip(test.columns,World3.SCALES.values())]
    print(test.columns,flush=True)
    
    test.plot(figsize=(10,7),grid=True,title="World 3 Model",xlabel="Year (CE)",ylabel="Value")

    plt.show()



