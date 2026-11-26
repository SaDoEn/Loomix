from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.storage.s3 import S3Storage, storage
from app.api.v1.routes import users
from app.api.v1.routes.media import router as media_router
from app.api.v1.routes.subscriptions import router as subscriptions_router
from app.api.v1.routes.interactions import router as interactions_router

app = FastAPI(title="Photo API")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(media_router, prefix="/api/v1")
app.include_router(subscriptions_router, prefix="/api/v1/subscriptions", tags=["Subscriptions"])
app.include_router(interactions_router, prefix="/api/v1", tags=["Interactions"])

@app.on_event("startup")
async def startup_event():
    await storage.init_bucket()

@app.get("/", response_class=HTMLResponse)
async def render_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/login", response_class=HTMLResponse)
async def render_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/register", response_class=HTMLResponse)
async def render_register(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def render_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/public_profile", response_class=HTMLResponse)
async def get_public_profile_page(request: Request):
    with open("templates/public_profile.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/search", response_class=HTMLResponse)
async def get_search_page(request: Request):
    with open("templates/search.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)