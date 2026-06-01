# Available packages in the sandbox (no pip install, no network)

The code-execution sandbox has these preinstalled (do NOT `pip install`, no network access):

Visualization: matplotlib 3.10.1, seaborn 0.13.2, plotly 6.1.2, bokeh 3.8.2
Data: numpy 2.1.3, pandas 2.2.3, scipy 1.15.2, scikit-learn 1.6.1
Image/IO: pillow 11.1.0, opencv-python 4.11.0.86, openpyxl 3.1.5, PyPDF2 3.0.1

Prefer **matplotlib** with the `Agg` backend for a single static PNG. Read input from
`data.json` in the working directory. Write the result as `output.png`.
