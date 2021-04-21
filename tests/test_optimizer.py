from .context import optimizer

#  {'data': [{'xi': [651, 56, 722, 'Ræv'], 'yi': 1}, {'xi': [651, 42, 722, 'Ræv'], 'yi': 0.2}], 'optimizerConfig': {'baseEstimator': 'GP', 'acqFunc': 'gp_hedge', 'initialPoints': 5, 'kappa': 1.96, 'xi': 0.012, 'space': [{'type': 'numeric', 'name': 'Sukker', 'from': 0, 'to': 1000}, {'type': 'numeric', 'name': 'Peber', 'from': 0, 'to': 1000}, {'type': 'numeric', 'name': 'Hvedemel', 'from': 0, 'to': 1000}, {'type': 'category', 'name': 'Kunde', 'categories': ['Mus', 'Ræv']}]}}

sampleData = [
        {'xi': [651, 56, 722, 'Ræv'], 'yi': 1}, 
        {'xi': [651, 42, 722, 'Ræv'], 'yi': 0.2}
        ]

sampleConfig = {
        'baseEstimator': 'GP', 
        'acqFunc': 
        'gp_hedge', 
        'initialPoints': 2, 
        'kappa': 1.96, 
        'xi': 0.012, 
        'space': [
            {'type': 'numeric', 'name': 'Sukker', 'from': 0, 'to': 1000}, 
            {'type': 'numeric', 'name': 'Peber', 'from': 0, 'to': 1000}, 
            {'type': 'numeric', 'name': 'Hvedemel', 'from': 0, 'to': 1000}, 
            {'type': 'category', 'name': 'Kunde', 'categories': ['Mus', 'Ræv']}
            ]
    }

samplePayload = {
    'data': sampleData, 
    'optimizerConfig': sampleConfig}

def validateResult(result):
    assert "plots" in result
    assert "result" in result
    assert "next" in result["result"]
    assert len(result["result"]["next"]) == len(sampleConfig["space"])
    assert "pickled" in result["result"]
    assert len(result["result"]["pickled"]) > 1

def test_can_be_run_without_data():
    result = optimizer.run(body={
        "data": [],
        "optimizerConfig": sampleConfig
        })
    validateResult(result)
    assert len(result["plots"]) ==  0

def test_generates_plots_when_run_with_more_than_initialPoints_samples():
    result = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig
        })
    validateResult(result)
    assert len(result["plots"]) ==  2
    