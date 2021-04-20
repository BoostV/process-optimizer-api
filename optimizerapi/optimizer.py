from json_tricks import dumps
from ProcessOptimizer import Optimizer, expected_minimum
from ProcessOptimizer.plots import plot_objective, plot_convergence
from ProcessOptimizer.utils import cook_estimator
from ProcessOptimizer.learning.gaussian_process.kernels import Matern
import matplotlib.pyplot as plt
import base64
import io 
from numbers import Number
import numpy
numpy.random.seed(42)
"""ProcessOptimizer web request handler

This file contains the main HTTP request handlers for exposing the ProcessOptimizer API.
The handler functions are mapped to the OpenAPI specification through the "operationId" field
in the specification.yml file found in the folder "openapi" in the root of this project.
"""

# def run(body) -> str:
#     print("Receive: " + body)
# def run(data: [([float], Number)] = [], space: [(float, float)] = [(0,1)], xi: float = 0.01, yi: Number = 1, kappa: float = 1.96) -> str:

def run(body) -> str:
    """Executes the ProcessOptimizer
    
    Returns
    -------
    str
        a JSON encoded string representation of the result.
    """
    # TODO generate space, i.e., an array of either options for categories or tuples of (min, max) for value types
    # Receive: {'data': [{'xi': [0], 'xi': 0}], 'optimizerConfig': {'acqFunc': 'string', 'baseEstimator': 'string', 'initialPoints': 0, 'kappa': 0, 'xi': 0}}
    # print("Receive: " + str(body))
    data = [(run["xi"], run["yi"]) for run in body["data"]]
    space = [(x["from"], x["to"]) for x in body["optimizerConfig"]["space"]]
    hyperparams = {
        'base_estimator': body["optimizerConfig"]["baseEstimator"],
        'acq_func': body["optimizerConfig"]["acqFunc"],
        'n_initial_points': body["optimizerConfig"]["initialPoints"],
        'acq_func_kwargs': {'kappa': body["optimizerConfig"]["kappa"], 'xi': body["optimizerConfig"]["xi"]}
    }
    optimizer = Optimizer(space, **hyperparams)
    # TODO ask seems to fail if there are only one entry - should the system auto generate the first entry?
    if data and len(data) > 1:
        Xi, Yi = map(list, zip(*data))
        result = optimizer.tell(Xi, Yi)
        response = processResult(result, optimizer)
    else:
        response = {}

    return dumps(response)

def processResult(result, optimizer):
    """Extracts results from the OptimizerResult.

    Parameters
    ----------
    result : OptimizerResult
        The result as it is returned from Optimizer.tell
    optimizer : ProcessOptimizer
        The instance used during the run. It contains the run configuration
        and parameters used.

    Returns
    -------
    dict
        a dictionary containing results and plots.
        The dictionary has this structure:
        {
            plots: [{id: plotname, plot: BASE64 encoded png}],
            result: { dict with relevant properties, e.g., 
                suggestions for next experiment, 
                model representation etc.}
        }
    """
    response = {
        "plots": []
    }
    prettyResult = {}
    response["result"] = prettyResult
    
    prettyResult["next"] = optimizer.ask(n_points=1)[0]

    ##################### Copied and modified from views.py::view_report #####################

    if "expected_minimum" in result:
        temp_exp_min =[]
        for entry,value in zip(header_list[:-1], result.expected_minimum[0]):
            temp_exp_min.append([entry, value])
        exp_min_out = {'value':temp_exp_min, 'result':result.expected_minimum[1]}
        prettyResult['expected_minimum'] = exp_min_out

    ##################### END #####################

    plot_convergence(result)
    addPlot(response["plots"], "convergence")

    dimensions = ["dim1", "dim2"]
    plot_objective(result, dimensions=dimensions, usepartialdependence=False)
    addPlot(response["plots"], "objective", debug=True)
    return response

def addPlot(result, id="generic", close=True, debug=False):
    """Add the current figure to result as a base64 encoded string.

    This function should be called after every plot that is generated.
    It takes the current state of the figure canvas and writes it to
    a base64 encoded string which is then appended to the list supplied.
    
    Parameters
    ----------
    result : list
        The list of plots to which new plots should be addeed.
    id : str
        Identifier for the plot (default is "generic")
    close : bool
        If set to True the current matplot figure is cleared after the plot
        has been saved. (default is True)
    debug : bool
        Indicate if plots should be written to local files. 
        If set to True plots are stored in tmp/process_optimizer_[id].png
        relative to current working directory. (default is False)
    """
    pic_IObytes = io.BytesIO()
    plt.savefig(pic_IObytes,  format='png')
    pic_IObytes.seek(0)
    pic_hash = base64.b64encode(pic_IObytes.read())
    result.append({
        "id": id,
        "plot": str(pic_hash, "utf-8")
    })

    if debug:
        with open('tmp/process_optimizer_' + id + '.png', 'wb') as imgfile:
            plt.savefig(imgfile,  bbox_inches='tight', pad_inches=0)

    # print("IMAGE: " + str(pic_hash, "utf-8"))
    if close:
        plt.clf()