import os
from uuid import uuid4
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import create_document, get_documents
from schemas import Message

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists and mount as static
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
def read_root():
    return {"message": "Chat backend is running"}


class MessageOut(BaseModel):
    id: Optional[str] = None
    username: str
    text: Optional[str] = None
    file_url: Optional[str] = None
    content_type: Optional[str] = None
    created_at: Optional[str] = None


@app.get("/api/messages")
def list_messages(limit: int = 50):
    try:
        docs = get_documents("message", {}, limit=limit)
        # Normalize Mongo docs
        out = []
        for d in docs:
            d_id = str(d.get("_id")) if d.get("_id") else None
            out.append({
                "id": d_id,
                "username": d.get("username"),
                "text": d.get("text"),
                "file_url": d.get("file_url"),
                "content_type": d.get("content_type"),
                "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
            })
        # return newest last
        out = sorted(out, key=lambda x: x.get("created_at") or "")
        return {"items": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/messages")
async def create_message(
    username: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    try:
        file_url = None
        content_type = None
        if file is not None:
            # Save file to uploads with safe unique name
            ext = os.path.splitext(file.filename or "")[1]
            fname = f"{uuid4().hex}{ext}"
            dest_path = os.path.join(UPLOAD_DIR, fname)
            with open(dest_path, "wb") as f:
                f.write(await file.read())
            file_url = f"/uploads/{fname}"
            content_type = file.content_type

        msg = Message(username=username, text=text, file_url=file_url, content_type=content_type)
        inserted_id = create_document("message", msg)
        return {"id": inserted_id, "ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
