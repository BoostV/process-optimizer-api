import os
import platform
from time import strftime
import json
import json_tricks
from ProcessOptimizer import Optimizer, expected_minimum
from ProcessOptimizer.plots import plot_objective, plot_convergence
import matplotlib.pyplot as plt
import base64
import io 
from numbers import Number
# from securepickle import pickleToString, unpickleFromString, get_crypto
import securepickle

import numpy
numpy.random.seed(42)

plt.switch_backend('Agg')

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
    # print("Receive: " + str(body))
    data = [(run["xi"], run["yi"]) for run in body["data"]]
    cfg = body["optimizerConfig"]
    extras = {}
    if ("extras" in body):
        extras = body["extras"]
    # print("Received extras " + str(extras))
    space = [(convertNumberType(x["from"], x["type"]), convertNumberType(x["to"], x["type"])) if (x["type"] == "discrete" or x["type"] == "continuous") else tuple(x["categories"]) for x in cfg["space"]]
    dimensions = [x["name"] for x in cfg["space"]]
    hyperparams = {
        'base_estimator': cfg["baseEstimator"],
        'acq_func': cfg["acqFunc"],
        'n_initial_points': cfg["initialPoints"],
        'acq_func_kwargs': {'kappa': cfg["kappa"], 'xi': cfg["xi"]}
    }
    optimizer = Optimizer(space, **hyperparams)

    Xi = []
    Yi = []
    if data:
        Xi, Yi = map(list, zip(*data))
        result = optimizer.tell(Xi, Yi)
    else:
        result = {}
    
    response = processResult(result, optimizer, dimensions, cfg, extras, data, space)
    
    response["result"]["extras"]["parameters"] = {
        "dimensions": dimensions,
        "space": space,
        "hyperparams": hyperparams,
        "Xi": Xi,
        "Yi": Yi,
        "extras": extras
    }

    # It is necesarry to convert response to a json string and then back to 
    # dictionary because NumPy types are not serializable by default
    return json.loads(json_tricks.dumps(response))

def convertNumberType(value, numType):
    if numType == "discrete":
        return int(value)
    else:
        return float(value)

def processResult(result, optimizer, dimensions, cfg, extras, data, space):
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
    extras: dict
        A dictionary containing "extra" non-specified values received from the client
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
    resultDetails = {
        "next": [],
        "pickled": "",
        "expected_minimum": [],
        "extras": {}
    }
    plots = []
    response = {
        "plots": plots,
        "result": resultDetails
    }
    
    # In the following section details that should be reported to 
    # clients should go into the "resultDetails" dictionary and plots
    # go into the "plots" list (this is handled by calling the "addPlot" function)
    experimentSuggestionCount = 1
    if ("experimentSuggestionCount" in extras):
        experimentSuggestionCount = extras["experimentSuggestionCount"]
    
    # print("Exp:" + str(experimentSuggestionCount))
    resultDetails["next"] = optimizer.ask(n_points=experimentSuggestionCount) # TODO Hent n_points fra brugeren

    if len(data) >= cfg["initialPoints"]:
        # Plotting is only possible if the model has 
        # processed more that "initialPoints" data points
        plot_convergence(result)
        addPlot(plots, "convergence")

        plot_objective(result, dimensions=dimensions, usepartialdependence=False)
        addPlot(plots, "objective")
    
    resultDetails["pickled"] = securepickle.pickleToString(result, securepickle.get_crypto())

    addVersionInfo(resultDetails["extras"])

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
    plt.savefig(pic_IObytes,  format='png', bbox_inches = 'tight')
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

def addVersionInfo(extras):
    """Add various version information to the dictionary supplied.
    
    Parameters
    ----------
    extras : dict
            The dictionary to hold the version information
    """
    
    with open("requirements-freeze.txt", "r") as requirementsFile:
        requirements = requirementsFile.readlines()
        extras["libraries"] = [x.rstrip() for x in requirements]

    extras["pythonVersion"] = platform.python_version()
    
    if os.path.isfile("version.txt"):
        with open("version.txt", "r") as versionFile:
            extras["apiVersion"] = versionFile.readline().rstrip()
    else:
        import subprocess
        try:
            extras["apiVersion"] = subprocess.check_output(["git", "describe", "--always"]).strip().decode()
        except:
            extras["apiVersion"] = 'Unknown development version'
    
    extras["timeOfExecution"] = strftime("%Y-%m-%d %H:%M:%S")