
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Simple EPI",
    description="Example API with 2 inputs and 2 outputs",
    version="1.0.0"
)



# Output data model
class OutputData(BaseModel):
    y1: float
    y2: float


@app.get("/predict")
def predict():
    # Example input dat
    x1=10
    x2=20
    # Example function with two inputs and two outputs
    y1 = x1 + x2
    y2 = x1 * x2

    return OutputData(
        y1=y1,
        y2=y2
    )
