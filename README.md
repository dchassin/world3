World3 Model
------------

World3 model developed by Meadows [1], updated by Branderhorst [2], and implemented by Vanwynsberghe [3].

Example
-------

The following input to Python

    import world3 as w3
    test = w3.World3()
    print(test)

outputs

                  population  resources   industry  agriculture  pollution
    1900-01-01  1.600000e+09   1.000000  41.562500   269.325000   0.183824
    1901-01-01  1.607237e+09   0.999717  42.314650   281.717904   0.107817
    1902-01-01  1.617208e+09   0.999428  44.092965   278.147142   0.068004
    1903-01-01  1.630342e+09   0.999125  45.588417   278.661263   0.047150
    1904-01-01  1.644874e+09   0.998809  46.970601   279.837458   0.036446
    ...                  ...        ...        ...          ...        ...
    2096-01-01  4.095846e+09   0.151635  12.757071   231.631933   0.741359
    2097-01-01  4.065166e+09   0.151413  12.144139   232.594775   0.703014
    2098-01-01  4.034825e+09   0.151204  11.561135   233.606877   0.666518
    2099-01-01  4.004811e+09   0.151005  11.006563   234.667747   0.631771
    2100-01-01  3.975108e+09   0.150818  10.479016   235.776673   0.598684

    [201 rows x 5 columns]

Marimo Notebook
---------------

To run the model in a [Marimo notebook](https://docs.marimo.io) run the following script:

    python3 -m venv .venv
    . .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    marimo run world3/notebook.py
    
References
----------

1. [Meadows, Donella H., Randers, Jorgen and Meadows, Dennis L. "The Limits to
Growth (1972)".](https://www.donellameadows.org/wp-content/userfiles/Limits-to-Growth-digital-scan-version.pdf)

2. [Branderhorst, Gaya. 2020. Update to Limits to Growth: Comparing the World3
Model With Empirical Data. Master's thesis, Harvard Extension School.](https://dash.harvard.edu/server/api/core/bitstreams/c5a728c0-e735-4bcf-bee8-b80ca370dbaf/content)

3. [PyWorld3, GitHub (2021). Accessed May 12 2026.](https://github.com/cvanwynsberghe/pyworld3)
