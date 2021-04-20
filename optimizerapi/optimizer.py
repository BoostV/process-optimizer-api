import json
from json_tricks import dumps
from ProcessOptimizer import Optimizer, expected_minimum
from ProcessOptimizer.plots import plot_objective, plot_convergence
from ProcessOptimizer.utils import cook_estimator
from ProcessOptimizer.learning.gaussian_process.kernels import Matern
import matplotlib.pyplot as plt
import base64
import io 
from numbers import Number
from securepickle import pickleToString, unpickleFromString, get_crypto

import numpy
numpy.random.seed(42)
"""ProcessOptimizer web request handler

This file contains the main HTTP request handlers for exposing the ProcessOptimizer API.
The handler functions are mapped to the OpenAPI specification through the "operationId" field
in the specification.yml file found in the folder "openapi" in the root of this project.
"""

def run(body) -> dict:
    """Executes the ProcessOptimizer
    
    Returns
    -------
    dict
        a JSON encodable dictionary representation of the result.
    """
    # TODO generate space, i.e., an array of either options for categories or tuples of (min, max) for value types
    print("Receive: " + str(body))
    data = [(run["xi"], run["yi"]) for run in body["data"]]
    cfg = body["optimizerConfig"]
    space = [(x["from"], x["to"]) if x["type"] == "numeric" else tuple(x["categories"]) for x in cfg["space"]]
    dimensions = [x["name"] for x in cfg["space"]]
    hyperparams = {
        'base_estimator': cfg["baseEstimator"],
        'acq_func': cfg["acqFunc"],
        'n_initial_points': cfg["initialPoints"],
        'acq_func_kwargs': {'kappa': cfg["kappa"], 'xi': cfg["xi"]}
    }
    optimizer = Optimizer(space, **hyperparams)

    if data:
        Xi, Yi = map(list, zip(*data))
        result = optimizer.tell(Xi, Yi)
    else:
        result = {}
    response = processResult(result, optimizer, dimensions, cfg, data, space)

    # It is necesarry to convert response to a json string and then back to dictionary because NumPy types are not serializable by default
    return json.loads(dumps(response))

def processResult(result, optimizer, dimensions, cfg, data, space):
    """Extracts results from the OptimizerResult.

    Parameters
    ----------
    result : OptimizerResult
        The result as it is returned from Optimizer.tell
    optimizer : ProcessOptimizer
        The instance used during the run. It contains the run configuration
        and parameters used.
    dimensions : list
        List of dimension names ordered to match space descriptor
    cfg : dict
        The configuration part of the user request
    data : list
        The data points that have been used in the result
    space : list
        The input space definition

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
    prettyResult = {
        "next": []
    }
    response["result"] = prettyResult
    
    prettyResult["next"] = optimizer.ask(n_points=1) # TODO Hent n_points fra brugeren

    ##################### Copied and modified from views.py::view_report #####################

    if "expected_minimum" in result:
        temp_exp_min =[]
        for entry,value in zip(header_list[:-1], result.expected_minimum[0]):
            temp_exp_min.append([entry, value])
        exp_min_out = {'value':temp_exp_min, 'result':result.expected_minimum[1]}
        prettyResult['expected_minimum'] = exp_min_out

    ##################### END #####################

    if len(data) >= cfg["initialPoints"]:
        # Plotting is only possible if the model has 
        # processed more that "initialPoints" data points
        plot_convergence(result)
        addPlot(response["plots"], "convergence")

        plot_objective(result, dimensions=dimensions, usepartialdependence=False)
        addPlot(response["plots"], "objective")
    
    prettyResult["pickled"] = pickleToString(result, get_crypto())
    # print(str(response))
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