from optimizerapi import optimizer

sampleConfig = {
    "acqFunc": "gp_hedge",
    "baseEstimator": "GP",
    "initialPoints": 3,
    "kappa": 0,
    "space": [
      {
        "from": 0,
        "to": 0
      }
    ],
    "xi": 0,
    "yi": 0
}

def test_first_sample():
    result = optimizer.run(body={
        "data": [],
        "optimizerConfig": sampleConfig
        })
    

def test_multiple_samples():
    result = optimizer.run(body={
        "data": [
            {
                "Xi": [0],
                "Yi": 0
            },
            {
                "Xi": [1],
                "Yi": 2
            }
            ],
        "optimizerConfig": sampleConfig
        })
    assert "plots" in result