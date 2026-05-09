"""FastAPI server — serves static dashboard + /api/investigate endpoint."""
import asyncio, sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.investigator import run_investigation

app = FastAPI(title="PESSOA API")
DASH_OUT = Path(__file__).parent.parent / "dashboard" / "out"


@app.get("/api/investigate/{property_id}", response_class=HTMLResponse)
async def investigate(property_id: int, email: bool = True):
    try:
        html = await asyncio.wait_for(
            asyncio.to_thread(run_investigation, property_id, send_email=email),
            timeout=250.0,
        )
        return HTMLResponse(content=html)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Investigation timed out (250s)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/", StaticFiles(directory=str(DASH_OUT), html=True), name="static")
