from fastapi import FastAPI
from fastapi.responses import JSONResponse

# L'instance "app" que votre fichier WSGI cherche à la ligne 12
app = FastAPI(title="Test Socadel Backend")

@app.get("/")
def read_root():
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Le backend Python fonctionne parfaitement sur PythonAnywhere !",
            "framework": "FastAPI"
        }
    )

@app.get("/api/test")
def test_api():
    return {"message": "La route d'API de test repond également !"}